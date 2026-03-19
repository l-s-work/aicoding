"""
订单相关 Pydantic Schemas
"""
from pydantic import BaseModel, field_validator
from typing import Optional


class OrderItemCreate(BaseModel):
    """订单明细项 (前端提交)"""
    product_id: int
    quantity: int
    
    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("购买数量必须大于 0")
        return v


class OrderCreate(BaseModel):
    """创建订单请求"""
    address_id: int  # 收货地址 ID
    items: list[OrderItemCreate]
    
    @field_validator("items")
    @classmethod
    def validate_items(cls, v: list[OrderItemCreate]) -> list[OrderItemCreate]:
        if len(v) == 0:
            raise ValueError("订单至少包含一件商品")
        return v


class OrderItemResponse(BaseModel):
    """订单明细响应"""
    id: int
    product_id: int
    product_name: str
    buy_price: float
    quantity: int
    created_at: str
    
    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """订单响应"""
    id: int
    order_no: str
    user_id: int
    total_amount: float
    status: str
    receiver_info: str  # JSON 字符串
    created_at: str
    updated_at: Optional[str] = None
    items: list[OrderItemResponse] = []
    
    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    """订单列表响应"""
    total: int
    items: list[OrderResponse]


class OrderStatusUpdate(BaseModel):
    """订单状态更新请求"""
    status: str
    
    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed_statuses = ["pending", "paid", "shipped", "completed", "cancelled"]
        if v not in allowed_statuses:
            raise ValueError(f"状态必须是以下之一: {', '.join(allowed_statuses)}")
        return v
