"""
订单服务层：核心业务逻辑
处理订单创建、库存扣减、快照保存等复杂事务
"""
import json
import random
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from fastapi import HTTPException, status

from app.db.models import Order, OrderItem, Product, UserAddress


async def generate_order_no(user_id: int) -> str:
    """
    生成订单号
    格式: YYYYMMDD + 用户ID后4位 + 6位随机数
    例: 20260318000112345
    """
    date_part = datetime.utcnow().strftime("%Y%m%d")
    user_part = str(user_id).zfill(4)[-4:]  # 取后4位，不足补0
    random_part = str(random.randint(100000, 999999))
    
    return f"{date_part}{user_part}{random_part}"


async def create_order_transaction(
    db: AsyncSession,
    user_id: int,
    address_id: int,
    items: list[dict],  # [{"product_id": int, "quantity": int}, ...]
) -> Order:
    """
    创建订单（完整事务）
    
    核心步骤：
    1. 原子扣减库存 (防超卖)
    2. 查询并校验收货地址归属
    3. 插入主订单 (含地址快照)
    4. 插入订单明细 (含价格快照)
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        address_id: 收货地址ID
        items: 订单商品列表
        
    Returns:
        创建的订单对象
        
    Raises:
        HTTPException: 库存不足、地址不存在等错误
    """
    # 使用 BEGIN IMMEDIATE 立即获取写锁，避免竞争窗口与文档描述不一致
    await db.execute(text("BEGIN IMMEDIATE"))
    try:
        # Step 1: 原子扣减库存
        total_amount = 0.0
        product_snapshots = []  # 保存商品快照信息

        for item in items:
            product_id = item["product_id"]
            quantity = item["quantity"]

            # 使用原子 UPDATE 扣减库存 (防超卖关键)
            stmt = (
                update(Product)
                .where(Product.id == product_id)
                .where(Product.stock >= quantity)  # 条件更新：库存充足
                .values(stock=Product.stock - quantity)
            )

            result = await db.execute(stmt)

            # 检查影响行数
            if result.rowcount == 0:
                # 查询商品以提供更详细的错误信息
                product_result = await db.execute(
                    select(Product).where(Product.id == product_id)
                )
                product = product_result.scalar_one_or_none()

                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"商品 ID {product_id} 不存在"
                    )

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"商品「{product.name}」库存不足（当前库存: {product.stock}，需要: {quantity}）"
                )

            # 查询商品信息（用于快照和计算总额）
            product_result = await db.execute(
                select(Product).where(Product.id == product_id)
            )
            product = product_result.scalar_one()

            # 保存商品快照
            product_snapshots.append({
                "product_id": product.id,
                "product_name": product.name,
                "buy_price": product.price,  # 下单时价格快照
                "quantity": quantity,
            })

            total_amount += product.price * quantity

        # Step 2: 查询并校验收货地址
        address_result = await db.execute(
            select(UserAddress).where(
                UserAddress.id == address_id,
                UserAddress.user_id == user_id
            )
        )
        address = address_result.scalar_one_or_none()

        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="收货地址不存在或不属于当前用户"
            )

        # 地址快照 (JSON 拍屏式硬拷贝)
        receiver_info = {
            "receiver_name": address.receiver_name,
            "phone": address.phone,
            "province": address.province,
            "city": address.city,
            "district": address.district,
            "detail_address": address.detail_address,
        }

        # Step 3: 插入主订单（含订单号冲突重试）
        order_no = None
        for _ in range(5):
            candidate = await generate_order_no(user_id)
            exists_result = await db.execute(
                select(Order.id).where(Order.order_no == candidate)
            )
            if exists_result.scalar_one_or_none() is None:
                order_no = candidate
                break
        if order_no is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="订单号生成失败，请稍后重试"
            )

        order = Order(
            order_no=order_no,
            user_id=user_id,
            total_amount=total_amount,
            status="pending",
            receiver_info=json.dumps(receiver_info, ensure_ascii=False),
            created_at=datetime.utcnow().isoformat(),
        )

        db.add(order)
        await db.flush()  # 获取 order.id

        # Step 4: 插入订单明细
        for snapshot in product_snapshots:
            order_item = OrderItem(
                order_id=order.id,
                product_id=snapshot["product_id"],
                product_name=snapshot["product_name"],
                buy_price=snapshot["buy_price"],
                quantity=snapshot["quantity"],
                created_at=datetime.utcnow().isoformat(),
            )
            db.add(order_item)

        # 提交事务
        await db.commit()
        await db.refresh(order)
        return order
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建订单失败: {str(exc)}"
        ) from exc


async def cancel_order_transaction(db: AsyncSession, order: Order) -> None:
    """
    取消订单（回滚库存）
    
    Args:
        db: 数据库会话
        order: 订单对象
        
    Raises:
        HTTPException: 订单状态不允许取消
    """
    # 只有 pending 状态的订单可以取消
    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有待支付订单可以取消"
        )
    
    await db.execute(text("BEGIN IMMEDIATE"))
    try:
        # 获取订单明细
        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()

        # 回滚库存
        for item in items:
            stmt = (
                update(Product)
                .where(Product.id == item.product_id)
                .values(stock=Product.stock + item.quantity)
            )
            await db.execute(stmt)

        # 更新订单状态
        order.status = "cancelled"
        order.updated_at = datetime.utcnow().isoformat()

        await db.commit()
    except Exception:
        await db.rollback()
        raise
