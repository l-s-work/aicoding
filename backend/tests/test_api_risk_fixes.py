"""
高风险问题回归测试（API 级）

覆盖目标：
- 订单支付状态流一致性（pending->paid + paid 幂等）
- 管理员订单状态机约束
- AI 向量同步接口权限收敛（普通用户禁止）
- 登出后 AT 拉黑生效
- 退出全部设备后 token_version 失效生效
- 默认地址唯一约束
- Refresh Cookie secure 配置生效
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers import _address, _admin, _ai, _auth, _order, _product
from app.core.config import settings
from app.core.security import create_access_token, decode_token, hash_password
from app.db.database import get_db
from app.db.models import (
    AccessTokenBlocklist,
    AccountRecoveryRequest,
    Order,
    Product,
    ProductCategory,
    RefreshToken,
    User,
    UserAddress,
)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _build_auth_header(user: User) -> tuple[dict[str, str], str]:
    token = create_access_token(
        {
            "user_id": user.id,
            "role": user.role,
            "token_version": user.token_version,
        }
    )
    return {"Authorization": f"Bearer {token}"}, token


async def _create_order(db: AsyncSession, user_id: int, status: str) -> Order:
    order = Order(
        order_no=f"TEST_{uuid4().hex[:12]}",
        user_id=user_id,
        total_amount=199.0,
        status=status,
        receiver_info='{"receiver_name":"测试用户"}',
        created_at=_now_iso(),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@pytest_asyncio.fixture
async def api_app(db_session: AsyncSession):
    app = FastAPI()
    for router in (_auth.router, _order.router, _ai.router, _address.router, _admin.router, _product.router):
        app.include_router(router, prefix="/api")

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client(api_app: FastAPI):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_pay_order_should_be_idempotent_when_order_already_paid(
    db_session: AsyncSession,
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    order = await _create_order(db_session, seed_user.id, status="paid")
    headers, _ = _build_auth_header(seed_user)

    response = await api_client.post(f"/api/orders/{order.id}/pay", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_pay_order_should_move_pending_to_paid(
    db_session: AsyncSession,
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    order = await _create_order(db_session, seed_user.id, status="pending")
    headers, _ = _build_auth_header(seed_user)

    response = await api_client.post(f"/api/orders/{order.id}/pay", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "paid"
    assert payload["updated_at"] is not None


@pytest.mark.asyncio
async def test_admin_update_order_status_should_reject_invalid_transition(
    db_session: AsyncSession,
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    admin = User(
        username="admin_1",
        email="admin_1@example.com",
        password_hash="hashed",
        role="admin",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    order = await _create_order(db_session, seed_user.id, status="paid")
    headers, _ = _build_auth_header(admin)

    # paid -> pending 不在管理员允许状态迁移矩阵中
    response = await api_client.put(
        f"/api/orders/admin/{order.id}/status",
        headers=headers,
        json={"status": "pending"},
    )
    assert response.status_code == 400
    assert "不允许从 paid 变更为 pending" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ai_sync_embedding_should_forbid_normal_user(
    db_session: AsyncSession,
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    product = Product(
        name="测试商品",
        description="测试描述",
        price=99.0,
        stock=5,
        status="on_sale",
        created_at=_now_iso(),
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    headers, _ = _build_auth_header(seed_user)
    response = await api_client.post(f"/api/ai/products/{product.id}/sync-embedding", headers=headers)
    assert response.status_code == 403
    assert "管理员" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout_should_block_current_access_token(
    db_session: AsyncSession,
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    headers, token = _build_auth_header(seed_user)

    logout_response = await api_client.post("/api/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    me_response = await api_client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 401

    token_payload = decode_token(token)
    token_jti = token_payload["jti"]
    blocked = (
        await db_session.execute(select(AccessTokenBlocklist).where(AccessTokenBlocklist.jti == token_jti))
    ).scalar_one_or_none()
    assert blocked is not None


@pytest.mark.asyncio
async def test_logout_all_should_invalidate_old_access_token(
    db_session: AsyncSession,
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    headers, _ = _build_auth_header(seed_user)

    logout_all_response = await api_client.post("/api/auth/logout-all", headers=headers)
    assert logout_all_response.status_code == 204

    me_response = await api_client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 401

    refreshed_user = (await db_session.execute(select(User).where(User.id == seed_user.id))).scalar_one()
    assert refreshed_user.token_version == 2


@pytest.mark.asyncio
async def test_user_default_address_should_be_unique_by_partial_index(
    db_session: AsyncSession,
    seed_user: User,
) -> None:
    addr_1 = UserAddress(
        user_id=seed_user.id,
        receiver_name="地址一",
        phone="13811110000",
        province="上海市",
        city="上海市",
        district="浦东新区",
        detail_address="A路1号",
        is_default=1,
        created_at=_now_iso(),
    )
    addr_2 = UserAddress(
        user_id=seed_user.id,
        receiver_name="地址二",
        phone="13811110001",
        province="上海市",
        city="上海市",
        district="徐汇区",
        detail_address="B路2号",
        is_default=1,
        created_at=_now_iso(),
    )
    db_session.add_all([addr_1, addr_2])

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_login_cookie_should_respect_cookie_secure_setting(
    db_session: AsyncSession,
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        username="cookie_user",
        email="cookie_user@example.com",
        password_hash=hash_password("CookiePass123"),
        role="client",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    db_session.add(user)
    await db_session.commit()

    # 通过配置控制 Cookie 安全属性，覆盖生产 HTTPS 要求。
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)

    response = await api_client.post(
        "/api/auth/login",
        json={"username": "cookie_user", "password": "CookiePass123"},
    )
    assert response.status_code == 200
    assert "Secure" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_address_routes_should_keep_single_default_address(
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    headers, _ = _build_auth_header(seed_user)

    first_resp = await api_client.post(
        "/api/addresses",
        headers=headers,
        json={
            "receiver_name": "地址A",
            "phone": "13812345001",
            "province": "上海市",
            "city": "上海市",
            "district": "浦东新区",
            "detail_address": "A路1号",
            "is_default": 1,
        },
    )
    assert first_resp.status_code == 201
    first_id = first_resp.json()["id"]

    second_resp = await api_client.post(
        "/api/addresses",
        headers=headers,
        json={
            "receiver_name": "地址B",
            "phone": "13812345002",
            "province": "上海市",
            "city": "上海市",
            "district": "徐汇区",
            "detail_address": "B路2号",
            "is_default": 1,
        },
    )
    assert second_resp.status_code == 201
    second_id = second_resp.json()["id"]

    list_resp = await api_client.get("/api/addresses", headers=headers)
    assert list_resp.status_code == 200
    addr_list = list_resp.json()
    assert len([item for item in addr_list if item["is_default"] == 1]) == 1
    assert any(item["id"] == second_id and item["is_default"] == 1 for item in addr_list)

    set_default_resp = await api_client.post(f"/api/addresses/{first_id}/set-default", headers=headers)
    assert set_default_resp.status_code == 200
    assert set_default_resp.json()["id"] == first_id
    assert set_default_resp.json()["is_default"] == 1


@pytest.mark.asyncio
async def test_admin_dashboard_stats_should_return_counts(
    db_session: AsyncSession,
    api_client: AsyncClient,
    seed_user: User,
) -> None:
    admin = User(
        username="admin_dash",
        email="admin_dash@example.com",
        password_hash="hashed",
        role="admin",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    category = ProductCategory(
        category_code="01-01-01",
        name="测试类目",
        level=3,
        created_at=_now_iso(),
    )
    product = Product(
        name="看板商品",
        description="用于测试看板统计",
        price=88.0,
        stock=9,
        status="on_sale",
        created_at=_now_iso(),
    )
    db_session.add_all([admin, category, product])
    await db_session.flush()
    product.category_id = category.id
    await db_session.commit()
    await db_session.refresh(admin)

    headers, _ = _build_auth_header(admin)
    resp = await api_client.get("/api/admin/dashboard/stats", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["product_total"] >= 1
    assert payload["category_total"] >= 1
    assert "status_distribution" in payload


@pytest.mark.asyncio
async def test_admin_users_status_should_block_self_disable(
    db_session: AsyncSession,
    api_client: AsyncClient,
) -> None:
    admin = User(
        username="admin_self",
        email="admin_self@example.com",
        password_hash="hashed",
        role="admin",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    headers, _ = _build_auth_header(admin)
    resp = await api_client.patch(
        f"/api/admin/users/{admin.id}/status",
        headers=headers,
        json={"is_active": 0},
    )
    assert resp.status_code == 400
    assert "不能封禁当前管理员账号" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_process_recovery_request_should_approve_and_unban_user(
    db_session: AsyncSession,
    api_client: AsyncClient,
) -> None:
    admin = User(
        username="admin_recovery",
        email="admin_recovery@example.com",
        password_hash="hashed",
        role="admin",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    banned_user = User(
        username="banned_user",
        email="banned_user@example.com",
        password_hash="hashed",
        role="client",
        token_version=1,
        is_active=0,
        failed_login_attempts=3,
        created_at=_now_iso(),
    )
    db_session.add_all([admin, banned_user])
    await db_session.flush()

    request_record = AccountRecoveryRequest(
        user_id=banned_user.id,
        username=banned_user.username,
        reason="请帮我恢复账号",
        status="pending",
        created_at=_now_iso(),
    )
    db_session.add(request_record)
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(request_record)

    headers, _ = _build_auth_header(admin)
    resp = await api_client.put(
        f"/api/admin/recovery-requests/{request_record.id}/process",
        headers=headers,
        json={"status": "approved", "admin_note": "审核通过"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    refreshed_user = (
        await db_session.execute(select(User).where(User.id == banned_user.id))
    ).scalar_one()
    assert refreshed_user.is_active == 1
    assert refreshed_user.token_version == 2


@pytest.mark.asyncio
async def test_auth_register_login_refresh_me_and_update_flow(
    api_client: AsyncClient,
) -> None:
    register_resp = await api_client.post(
        "/api/auth/register",
        json={
            "username": "new_user_1",
            "email": "new_user_1@example.com",
            "password": "TestPass123",
        },
    )
    assert register_resp.status_code == 201
    user_id = register_resp.json()["id"]

    # 重复注册应被拒绝
    duplicate_resp = await api_client.post(
        "/api/auth/register",
        json={
            "username": "new_user_1",
            "email": "another@example.com",
            "password": "TestPass123",
        },
    )
    assert duplicate_resp.status_code == 409

    login_resp = await api_client.post(
        "/api/auth/login",
        json={"username": "new_user_1", "password": "TestPass123"},
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    assert "refresh_token=" in login_resp.headers.get("set-cookie", "")

    me_resp = await api_client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == user_id

    refresh_resp = await api_client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 200
    assert isinstance(refresh_resp.json().get("access_token"), str)

    update_me_resp = await api_client.put(
        "/api/auth/me",
        headers=headers,
        json={"username": "new_user_1_renamed", "email": "new_user_1_renamed@example.com"},
    )
    assert update_me_resp.status_code == 200
    assert update_me_resp.json()["username"] == "new_user_1_renamed"


@pytest.mark.asyncio
async def test_auth_forgot_password_and_change_password_should_revoke_sessions(
    db_session: AsyncSession,
    api_client: AsyncClient,
) -> None:
    user = User(
        username="change_pwd_user",
        email="change_pwd_user@example.com",
        password_hash=hash_password("OldPass123"),
        role="client",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 先登录一次，产生 refresh token 记录
    login_resp = await api_client.post(
        "/api/auth/login",
        json={"username": "change_pwd_user", "password": "OldPass123"},
    )
    assert login_resp.status_code == 200
    old_access_token = login_resp.json()["access_token"]
    old_headers = {"Authorization": f"Bearer {old_access_token}"}

    token_count_before = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert len(token_count_before) >= 1

    forgot_resp = await api_client.post(
        "/api/auth/forgot-password",
        json={
            "username": "change_pwd_user",
            "email": "change_pwd_user@example.com",
            "new_password": "NewPass123",
        },
    )
    assert forgot_resp.status_code == 204

    refreshed_user = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed_user.token_version == 2
    token_count_after_forgot = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert len(token_count_after_forgot) == 0

    # 旧 AT 应立即失效
    me_with_old_token_resp = await api_client.get("/api/auth/me", headers=old_headers)
    assert me_with_old_token_resp.status_code == 401

    # 使用新密码登录，再测试 change-password 的会话吊销
    relogin_resp = await api_client.post(
        "/api/auth/login",
        json={"username": "change_pwd_user", "password": "NewPass123"},
    )
    assert relogin_resp.status_code == 200
    new_headers = {"Authorization": f"Bearer {relogin_resp.json()['access_token']}"}

    wrong_change_resp = await api_client.post(
        "/api/auth/change-password",
        headers=new_headers,
        json={"current_password": "WrongPass123", "new_password": "NewestPass123"},
    )
    assert wrong_change_resp.status_code == 400

    ok_change_resp = await api_client.post(
        "/api/auth/change-password",
        headers=new_headers,
        json={"current_password": "NewPass123", "new_password": "NewestPass123"},
    )
    assert ok_change_resp.status_code == 204

    me_after_change_resp = await api_client.get("/api/auth/me", headers=new_headers)
    assert me_after_change_resp.status_code == 401


@pytest.mark.asyncio
async def test_product_category_tree_and_crud_flow(
    db_session: AsyncSession,
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    admin = User(
        username="admin_product",
        email="admin_product@example.com",
        password_hash="hashed",
        role="admin",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    admin_headers, _ = _build_auth_header(admin)

    async def fake_upsert_embedding_status(db: AsyncSession, product_id: int, status: str):
        return None

    async def fake_trigger_embedding_sync(product_id: int, force: bool):
        return None

    monkeypatch.setattr(_product, "upsert_embedding_status", fake_upsert_embedding_status)
    monkeypatch.setattr(_product, "trigger_product_embedding_sync", fake_trigger_embedding_sync)
    # 上传测试文件落到临时目录，避免污染仓库中的 uploads 资源。
    monkeypatch.setattr(_product, "PRODUCT_UPLOAD_DIR", tmp_path / "uploads" / "products")

    level1_resp = await api_client.post(
        "/api/products/categories",
        headers=admin_headers,
        json={"name": "数码", "sort_order": 1},
    )
    assert level1_resp.status_code == 201
    level1_id = level1_resp.json()["id"]

    level2_resp = await api_client.post(
        "/api/products/categories",
        headers=admin_headers,
        json={"name": "耳机", "parent_id": level1_id, "sort_order": 1},
    )
    assert level2_resp.status_code == 201
    level2_id = level2_resp.json()["id"]

    level3_resp = await api_client.post(
        "/api/products/categories",
        headers=admin_headers,
        json={"name": "蓝牙耳机", "parent_id": level2_id, "sort_order": 1},
    )
    assert level3_resp.status_code == 201
    level3_id = level3_resp.json()["id"]

    full_tree_resp = await api_client.get("/api/products/categories")
    assert full_tree_resp.status_code == 200
    assert len(full_tree_resp.json()) >= 1

    level_filter_resp = await api_client.get("/api/products/categories", params={"level": 3})
    assert level_filter_resp.status_code == 200
    assert any(item["id"] == level3_id for item in level_filter_resp.json())

    product_create_resp = await api_client.post(
        "/api/products",
        headers=admin_headers,
        json={
            "name": "降噪蓝牙耳机",
            "description": "40dB 主动降噪",
            "price": 599.0,
            "stock": 20,
            "category_id": level3_id,
            "status": "on_sale",
        },
    )
    assert product_create_resp.status_code == 201
    created_product = product_create_resp.json()
    product_id = created_product["id"]

    list_resp = await api_client.get(
        "/api/products",
        params={"keyword": "降噪", "category_id": level1_id, "page": 1, "page_size": 20},
    )
    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert list_payload["total"] >= 1

    detail_resp = await api_client.get(f"/api/products/{product_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == "降噪蓝牙耳机"

    update_resp = await api_client.put(
        f"/api/products/{product_id}",
        headers=admin_headers,
        json={"name": "降噪蓝牙耳机 Pro", "description": "升级版"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "降噪蓝牙耳机 Pro"

    manual_sync_resp = await api_client.post(
        f"/api/products/{product_id}/embedding/sync",
        headers=admin_headers,
    )
    assert manual_sync_resp.status_code == 202

    upload_resp = await api_client.post(
        "/api/products/upload-image",
        headers=admin_headers,
        files={"file": ("test.png", b"fake-image-content", "image/png")},
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["url"].startswith("/uploads/products/")

    delete_resp = await api_client.delete(f"/api/products/{product_id}", headers=admin_headers)
    assert delete_resp.status_code == 204
