"""
订单服务单元测试

覆盖重点：
- 原子扣减库存与事务回滚
- 地址/价格快照固化
- 订单号冲突重试
- 取消订单库存回滚
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order, OrderItem, Product, UserAddress
from app.services import order_service
from app.services.order_service import cancel_order_transaction, create_order_transaction


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@pytest.mark.asyncio
async def test_create_order_success_should_snapshot_and_deduct_stock(
    db_session: AsyncSession,
    seed_user,
    seed_product,
    seed_address,
) -> None:
    order = await create_order_transaction(
        db=db_session,
        user_id=seed_user.id,
        address_id=seed_address.id,
        items=[{"product_id": seed_product.id, "quantity": 2}],
    )

    assert order.status == "paid"
    assert order.total_amount == pytest.approx(798.0)

    product_result = await db_session.execute(select(Product).where(Product.id == seed_product.id))
    product = product_result.scalar_one()
    assert product.stock == 8

    item_result = await db_session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    order_item = item_result.scalar_one()
    assert order_item.product_id == seed_product.id
    assert order_item.product_name == "测试降噪耳机"
    assert order_item.buy_price == pytest.approx(399.0)
    assert order_item.quantity == 2

    receiver = json.loads(order.receiver_info)
    assert receiver["receiver_name"] == "张三"
    assert receiver["detail_address"] == "世纪大道 100 号"

    # 修改地址与商品，确认历史订单快照不被污染
    seed_address.detail_address = "南京西路 200 号"
    seed_product.price = 9999.0
    await db_session.commit()

    reloaded_order = (await db_session.execute(select(Order).where(Order.id == order.id))).scalar_one()
    reloaded_item = (await db_session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalar_one()
    reloaded_receiver = json.loads(reloaded_order.receiver_info)
    assert reloaded_receiver["detail_address"] == "世纪大道 100 号"
    assert reloaded_item.buy_price == pytest.approx(399.0)


@pytest.mark.asyncio
async def test_create_order_should_rollback_when_stock_not_enough(
    db_session: AsyncSession,
    seed_user,
    seed_address,
) -> None:
    p1 = Product(name="商品A", price=100.0, stock=5, status="on_sale", created_at=_now_iso())
    p2 = Product(name="商品B", price=200.0, stock=1, status="on_sale", created_at=_now_iso())
    db_session.add_all([p1, p2])
    await db_session.commit()
    await db_session.refresh(p1)
    await db_session.refresh(p2)
    p1_id = p1.id
    p2_id = p2.id

    with pytest.raises(HTTPException) as exc:
        await create_order_transaction(
            db=db_session,
            user_id=seed_user.id,
            address_id=seed_address.id,
                items=[
                    {"product_id": p1_id, "quantity": 2},
                    {"product_id": p2_id, "quantity": 2},
                ],
            )

    assert exc.value.status_code == 400
    assert "库存不足" in str(exc.value.detail)

    p1_after = (await db_session.execute(select(Product).where(Product.id == p1_id))).scalar_one()
    p2_after = (await db_session.execute(select(Product).where(Product.id == p2_id))).scalar_one()
    assert p1_after.stock == 5
    assert p2_after.stock == 1

    orders = (await db_session.execute(select(Order))).scalars().all()
    assert orders == []


@pytest.mark.asyncio
async def test_create_order_should_return_404_when_product_not_exists(
    db_session: AsyncSession,
    seed_user,
    seed_address,
) -> None:
    with pytest.raises(HTTPException) as exc:
        await create_order_transaction(
            db=db_session,
            user_id=seed_user.id,
            address_id=seed_address.id,
            items=[{"product_id": 99999, "quantity": 1}],
        )

    assert exc.value.status_code == 404
    assert "不存在" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_create_order_should_rollback_when_address_not_owned(
    db_session: AsyncSession,
    seed_user,
    seed_second_user,
    seed_product,
) -> None:
    seed_product_id = seed_product.id
    foreign_address = UserAddress(
        user_id=seed_second_user.id,
        receiver_name="李四",
        phone="13912345678",
        province="北京市",
        city="北京市",
        district="朝阳区",
        detail_address="建国路 1 号",
        is_default=1,
        created_at=_now_iso(),
    )
    db_session.add(foreign_address)
    await db_session.commit()
    await db_session.refresh(foreign_address)

    with pytest.raises(HTTPException) as exc:
        await create_order_transaction(
            db=db_session,
            user_id=seed_user.id,
            address_id=foreign_address.id,
            items=[{"product_id": seed_product_id, "quantity": 1}],
        )

    assert exc.value.status_code == 404
    assert "收货地址不存在" in str(exc.value.detail)

    product_after = (await db_session.execute(select(Product).where(Product.id == seed_product_id))).scalar_one()
    assert product_after.stock == 10


@pytest.mark.asyncio
async def test_create_order_should_retry_when_order_no_collides(
    db_session: AsyncSession,
    seed_user,
    seed_address,
    seed_product,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_order = Order(
        order_no="DUPLICATE_ORDER_NO",
        user_id=seed_user.id,
        total_amount=1.0,
        status="paid",
        receiver_info="{}",
        created_at=_now_iso(),
    )
    db_session.add(existing_order)
    await db_session.commit()

    generated = iter(["DUPLICATE_ORDER_NO", "UNIQUE_ORDER_NO"])

    async def fake_generate_order_no(_user_id: int) -> str:
        return next(generated)

    monkeypatch.setattr(order_service, "generate_order_no", fake_generate_order_no)

    order = await create_order_transaction(
        db=db_session,
        user_id=seed_user.id,
        address_id=seed_address.id,
        items=[{"product_id": seed_product.id, "quantity": 1}],
    )
    assert order.order_no == "UNIQUE_ORDER_NO"


@pytest.mark.asyncio
async def test_create_order_should_fail_after_retry_exhausted(
    db_session: AsyncSession,
    seed_user,
    seed_address,
    seed_product,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_product_id = seed_product.id
    existing_order = Order(
        order_no="ALWAYS_DUPLICATE",
        user_id=seed_user.id,
        total_amount=1.0,
        status="paid",
        receiver_info="{}",
        created_at=_now_iso(),
    )
    db_session.add(existing_order)
    await db_session.commit()

    async def fake_generate_order_no(_user_id: int) -> str:
        return "ALWAYS_DUPLICATE"

    monkeypatch.setattr(order_service, "generate_order_no", fake_generate_order_no)

    with pytest.raises(HTTPException) as exc:
        await create_order_transaction(
            db=db_session,
            user_id=seed_user.id,
            address_id=seed_address.id,
            items=[{"product_id": seed_product_id, "quantity": 1}],
        )

    assert exc.value.status_code == 500
    assert "订单号生成失败" in str(exc.value.detail)

    # 订单失败后库存需回滚
    product_after = (await db_session.execute(select(Product).where(Product.id == seed_product_id))).scalar_one()
    assert product_after.stock == 10


@pytest.mark.asyncio
async def test_cancel_order_should_restore_stock_and_set_cancelled(
    db_session: AsyncSession,
    seed_user,
    seed_product,
) -> None:
    seed_product.stock = 3
    order = Order(
        order_no="ORDER_TO_CANCEL_1",
        user_id=seed_user.id,
        total_amount=798.0,
        status="paid",
        receiver_info="{}",
        created_at=_now_iso(),
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=seed_product.id,
        product_name=seed_product.name,
        buy_price=399.0,
        quantity=2,
        created_at=_now_iso(),
    )
    db_session.add(item)
    await db_session.commit()

    await cancel_order_transaction(db_session, order)

    product_after = (await db_session.execute(select(Product).where(Product.id == seed_product.id))).scalar_one()
    order_after = (await db_session.execute(select(Order).where(Order.id == order.id))).scalar_one()
    assert product_after.stock == 5
    assert order_after.status == "cancelled"
    assert order_after.updated_at is not None


@pytest.mark.asyncio
async def test_cancel_order_should_reject_invalid_status(
    db_session: AsyncSession,
    seed_user,
) -> None:
    order = Order(
        order_no="ORDER_INVALID_CANCEL_1",
        user_id=seed_user.id,
        total_amount=100.0,
        status="shipped",
        receiver_info="{}",
        created_at=_now_iso(),
    )
    db_session.add(order)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await cancel_order_transaction(db_session, order)

    assert exc.value.status_code == 400
    assert "可以取消" in str(exc.value.detail)
