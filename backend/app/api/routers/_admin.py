"""
管理员路由：Dashboard 统计、用户管理
"""
from datetime import datetime
from sqlalchemy import select, func, and_, or_
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentAdmin, DatabaseSession
from app.db.models import Product, ProductCategory, User, AccountRecoveryRequest
from app.core.security import hash_password
from app.schemas.admin_schema import (
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusUpdate,
    AdminResetPasswordRequest,
    DashboardStatsResponse,
    ProductStatusCount,
    CategoryProductCount,
    HotProductItem,
    RecoveryRequestListResponse,
    RecoveryRequestResponse,
    RecoveryRequestProcessRequest,
)

router = APIRouter(prefix="/admin", tags=["管理员"])


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db: DatabaseSession, admin: CurrentAdmin):
    """获取管理员看板统计数据（以商品统计为主）"""
    product_total = (await db.execute(select(func.count()).select_from(Product))).scalar() or 0
    on_sale_total = (
        await db.execute(select(func.count()).select_from(Product).where(Product.status == "on_sale"))
    ).scalar() or 0
    off_sale_total = (
        await db.execute(select(func.count()).select_from(Product).where(Product.status == "off_sale"))
    ).scalar() or 0
    low_stock_total = (
        await db.execute(
            select(func.count()).select_from(Product).where(and_(Product.stock > 0, Product.stock <= 10))
        )
    ).scalar() or 0
    out_of_stock_total = (
        await db.execute(select(func.count()).select_from(Product).where(Product.stock <= 0))
    ).scalar() or 0
    category_total = (await db.execute(select(func.count()).select_from(ProductCategory))).scalar() or 0

    status_rows = (
        await db.execute(
            select(Product.status, func.count(Product.id))
            .group_by(Product.status)
            .order_by(Product.status)
        )
    ).all()
    status_distribution = [ProductStatusCount(status=row[0], count=row[1]) for row in status_rows]

    category_rows = (
        await db.execute(
            select(
                ProductCategory.id,
                ProductCategory.name,
                func.count(Product.id),
            )
            .outerjoin(Product, Product.category_id == ProductCategory.id)
            .group_by(ProductCategory.id, ProductCategory.name)
            .order_by(func.count(Product.id).desc(), ProductCategory.id.asc())
            .limit(8)
        )
    ).all()
    top_categories = [
        CategoryProductCount(
            category_id=row[0],
            category_name=row[1],
            product_count=row[2],
        )
        for row in category_rows
    ]

    hot_rows = (
        await db.execute(
            select(Product.id, Product.name, Product.hot_score, Product.stock, Product.status)
            .order_by(Product.hot_score.desc(), Product.id.desc())
            .limit(10)
        )
    ).all()
    top_hot_products = [
        HotProductItem(id=row[0], name=row[1], hot_score=row[2], stock=row[3], status=row[4])
        for row in hot_rows
    ]

    return DashboardStatsResponse(
        product_total=product_total,
        on_sale_total=on_sale_total,
        off_sale_total=off_sale_total,
        low_stock_total=low_stock_total,
        out_of_stock_total=out_of_stock_total,
        category_total=category_total,
        status_distribution=status_distribution,
        top_categories=top_categories,
        top_hot_products=top_hot_products,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def get_users(
    db: DatabaseSession,
    admin: CurrentAdmin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="用户名/邮箱模糊搜索"),
    is_active: int | None = Query(None, description="账号状态过滤：1正常，0封禁"),
):
    """管理员查询用户列表（支持模糊搜索、状态筛选）"""
    query = select(User)
    if keyword:
        kw = f"%{keyword}%"
        query = query.where(or_(User.username.like(kw), User.email.like(kw)))
    if is_active in (0, 1):
        query = query.where(User.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0

    offset = (page - 1) * page_size
    rows = await db.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    users = rows.scalars().all()
    return AdminUserListResponse(total=total, items=[AdminUserResponse.model_validate(u) for u in users])


@router.patch("/users/{user_id}/status", response_model=AdminUserResponse)
async def update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdate,
    db: DatabaseSession,
    admin: CurrentAdmin,
):
    """管理员封禁/解封用户"""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.id == admin.id and payload.is_active == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能封禁当前管理员账号")

    user.is_active = payload.is_active
    if payload.is_active == 0:
        # 封禁时立刻使全部旧 token 失效
        user.token_version += 1
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    db: DatabaseSession,
    admin: CurrentAdmin,
):
    """管理员重置用户密码"""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.password_hash = hash_password(payload.new_password)
    # 重置密码后踢下线所有会话
    user.token_version += 1
    await db.commit()


@router.get("/recovery-requests", response_model=RecoveryRequestListResponse)
async def get_recovery_requests(
    db: DatabaseSession,
    admin: CurrentAdmin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status", description="pending/approved/rejected"),
):
    """管理员查看账号恢复申请列表"""
    query = select(AccountRecoveryRequest)
    if status_filter in ("pending", "approved", "rejected"):
        query = query.where(AccountRecoveryRequest.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    offset = (page - 1) * page_size
    rows = await db.execute(
        query.order_by(AccountRecoveryRequest.created_at.desc()).offset(offset).limit(page_size)
    )
    requests = rows.scalars().all()
    return RecoveryRequestListResponse(total=total, items=[RecoveryRequestResponse.model_validate(item) for item in requests])


@router.put("/recovery-requests/{request_id}/process", response_model=RecoveryRequestResponse)
async def process_recovery_request(
    request_id: int,
    payload: RecoveryRequestProcessRequest,
    db: DatabaseSession,
    admin: CurrentAdmin,
):
    """管理员处理账号恢复申请（通过/驳回）"""
    request_record = (
        await db.execute(select(AccountRecoveryRequest).where(AccountRecoveryRequest.id == request_id))
    ).scalar_one_or_none()
    if not request_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="恢复申请不存在")
    if request_record.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该申请已处理")

    request_record.status = payload.status
    request_record.admin_note = payload.admin_note.strip() if payload.admin_note else None
    request_record.processed_by = admin.id
    request_record.processed_at = datetime.utcnow().isoformat()

    if payload.status == "approved":
        user = (await db.execute(select(User).where(User.id == request_record.user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="申请关联用户不存在")
        user.is_active = 1
        user.failed_login_attempts = 0
        user.lockout_until = None
        user.token_version += 1

    await db.commit()
    await db.refresh(request_record)
    return RecoveryRequestResponse.model_validate(request_record)
