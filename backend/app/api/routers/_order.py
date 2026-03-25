"""
订单路由：创建订单、查询订单、管理订单
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.api.deps import DatabaseSession, CurrentUser, CurrentAdmin
from app.db.models import Order, OrderItem, Product, User
from app.schemas.order_schema import (
    OrderCreate, OrderResponse, OrderListResponse, OrderStatusUpdate
)
from app.services.order_service import create_order_transaction, cancel_order_transaction

router = APIRouter(prefix="/orders", tags=["订单"])

# 管理员可执行的订单状态迁移矩阵。
# 设计原则：
# 1. 已完成状态只能由用户确认收货触发（shipped -> completed）
# 2. 管理员负责“运营流转”：待处理/已支付 -> 发货/取消
# 3. 允许同状态幂等更新，避免重复点击导致误报
ADMIN_ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"paid", "cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": set(),
    "completed": set(),
    "cancelled": set(),
}


def _attach_username(order: Order) -> None:
    """给订单对象附加 username 字段，便于响应模型直接返回"""
    if getattr(order, "user", None) is not None:
        order.username = order.user.username


def _order_response_options():
    """预加载订单响应所需的关系，避免懒加载触发异步错误。"""
    return (
        selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.category),
        selectinload(Order.user),
    )


def _attach_order_item_categories(order: Order) -> None:
    """把商品分类名挂到订单明细上，方便前端直接展示。"""
    for item in getattr(order, "items", []):
        product = getattr(item, "product", None)
        category = getattr(product, "category", None)
        item.category_name = getattr(category, "name", None)


async def _load_order_for_user(db: DatabaseSession, order_id: int, *, user_id: Optional[int] = None) -> Order | None:
    """按照订单 ID 重新加载完整订单对象。"""
    query = select(Order).options(*_order_response_options()).where(Order.id == order_id)
    if user_id is not None:
        query = query.where(Order.user_id == user_id)

    result = await db.execute(query)
    order = result.scalar_one_or_none()
    if order is not None:
        _attach_username(order)
        _attach_order_item_categories(order)
    return order


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    db: DatabaseSession,
    current_user: CurrentUser
):
    """
    创建订单
    
    - 验证库存并原子扣减
    - 保存地址快照和价格快照
    - 生成唯一订单号
    """
    # 将 Pydantic 模型转为字典
    items = [{"product_id": item.product_id, "quantity": item.quantity} 
             for item in order_data.items]
    
    # 调用服务层创建订单 (事务)
    order = await create_order_transaction(
        db=db,
        user_id=current_user.id,
        address_id=order_data.address_id,
        items=items
    )

    loaded_order = await _load_order_for_user(db, order.id, user_id=current_user.id)
    return loaded_order or order


@router.get("", response_model=OrderListResponse)
async def get_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="订单状态筛选"),
    product_name: Optional[str] = Query(None, description="按商品名称模糊搜索"),
    db: DatabaseSession = None,
    current_user: CurrentUser = None
):
    """
    获取当前用户的订单列表
    
    - 支持分页
    - 支持按状态筛选
    """
    query = select(Order).where(Order.user_id == current_user.id)
    
    if status:
        query = query.where(Order.status == status)
    if product_name:
        kw = f"%{product_name}%"
        query = query.where(
            Order.items.any(OrderItem.product_name.like(kw))
        )
    
    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页查询（按创建时间倒序）
    offset = (page - 1) * page_size
    query = query.order_by(Order.created_at.desc())
    query = query.offset(offset).limit(page_size)
    query = query.options(*_order_response_options())  # 预加载订单明细+用户
    
    result = await db.execute(query)
    orders = result.scalars().all()
    for order in orders:
        _attach_username(order)
        _attach_order_item_categories(order)
    
    return OrderListResponse(total=total, items=orders)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, db: DatabaseSession, current_user: CurrentUser):
    """获取订单详情"""
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(*_order_response_options())
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    
    _attach_username(order)
    _attach_order_item_categories(order)
    return order


@router.post("/{order_id}/pay", response_model=OrderResponse)
async def pay_order(order_id: int, db: DatabaseSession, current_user: CurrentUser):
    """
    假支付接口（兼容模式）

    - pending -> paid
    - paid 直接幂等返回（兼容“下单即已支付”的当前业务）
    - 其他状态拒绝支付
    """
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(*_order_response_options())
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    
    if order.status == "paid":
        _attach_username(order)
        _attach_order_item_categories(order)
        return order

    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前状态不允许支付（当前: {order.status}）"
        )
    
    order.status = "paid"
    order.updated_at = datetime.utcnow().isoformat()
    
    await db.commit()
    loaded_order = await _load_order_for_user(db, order.id, user_id=current_user.id)
    return loaded_order or order


@router.post("/{order_id}/confirm-receipt", response_model=OrderResponse)
async def confirm_order_receipt(order_id: int, db: DatabaseSession, current_user: CurrentUser):
    """
    用户确认收货

    - 仅已发货订单允许确认收货
    - 确认后状态改为 completed
    """
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(*_order_response_options())
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    if order.status != "shipped":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有已发货订单可以确认收货"
        )

    order.status = "completed"
    order.updated_at = datetime.utcnow().isoformat()
    await db.commit()
    loaded_order = await _load_order_for_user(db, order.id, user_id=current_user.id)
    return loaded_order or order


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(order_id: int, db: DatabaseSession, current_user: CurrentUser):
    """
    取消订单
    
    - 只能取消待支付/已支付（未发货）订单
    - 自动回滚库存
    """
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(*_order_response_options())
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
    )
    
    await cancel_order_transaction(db, order)
    loaded_order = await _load_order_for_user(db, order.id, user_id=current_user.id)
    return loaded_order or order


# ==================== 管理员接口 ====================

@router.get("/admin/all", response_model=OrderListResponse)
async def get_all_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    receiver_name: Optional[str] = Query(None, description="按收货人/用户名模糊搜索"),
    product_name: Optional[str] = Query(None, description="按商品名称模糊搜索"),
    db: DatabaseSession = None,
    admin: CurrentAdmin = None
):
    """
    管理员查看所有订单
    """
    query = select(Order).join(User, User.id == Order.user_id)
    
    if status:
        query = query.where(Order.status == status)
    if receiver_name:
        kw = f"%{receiver_name}%"
        query = query.where(
            or_(
                User.username.like(kw),
                Order.receiver_info.like(kw),
            )
        )
    if product_name:
        kw = f"%{product_name}%"
        query = query.where(
            Order.items.any(OrderItem.product_name.like(kw))
        )
    
    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(Order.created_at.desc())
    query = query.offset(offset).limit(page_size)
    query = query.options(*_order_response_options())
    
    result = await db.execute(query)
    orders = result.scalars().all()
    for order in orders:
        _attach_username(order)
        _attach_order_item_categories(order)
    
    return OrderListResponse(total=total, items=orders)


@router.get("/admin/{order_id}", response_model=OrderResponse)
async def get_admin_order_detail(order_id: int, db: DatabaseSession, admin: CurrentAdmin):
    """管理员查看订单详情"""
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(*_order_response_options())
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    _attach_username(order)
    _attach_order_item_categories(order)
    return order


@router.put("/admin/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    db: DatabaseSession,
    admin: CurrentAdmin
):
    """
    管理员更新订单状态
    
    - 发货: paid → shipped
    - 已完成状态只能由用户确认收货触发
    - 已完成订单禁止再次修改
    """
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(*_order_response_options())
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    # “已完成”应由用户确认收货触发，管理员不可直接设置
    if status_data.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已完成状态需由用户确认收货触发"
        )

    # 同状态更新按幂等处理，直接返回当前订单，避免重复操作报错
    if status_data.status == order.status:
        _attach_username(order)
        _attach_order_item_categories(order)
        return order

    allowed_targets = ADMIN_ALLOWED_STATUS_TRANSITIONS.get(order.status, set())
    if status_data.status not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"订单状态不允许从 {order.status} 变更为 {status_data.status}"
        )

    order.status = status_data.status
    order.updated_at = datetime.utcnow().isoformat()
    
    await db.commit()
    loaded_order = await _load_order_for_user(db, order.id)
    return loaded_order or order
