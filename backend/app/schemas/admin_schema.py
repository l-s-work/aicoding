"""
管理员相关 Pydantic Schemas
"""
from pydantic import BaseModel, Field, field_validator
import re


class AdminUserResponse(BaseModel):
    """管理员视角用户信息"""
    id: int
    username: str
    email: str
    role: str
    is_active: int
    created_at: str

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """用户列表响应"""
    total: int
    items: list[AdminUserResponse]


class AdminUserStatusUpdate(BaseModel):
    """封禁/解封用户"""
    is_active: int = Field(description="1=启用，0=封禁")

    @field_validator("is_active")
    @classmethod
    def validate_is_active(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("is_active 只能是 0 或 1")
        return v


class AdminResetPasswordRequest(BaseModel):
    """管理员重置用户密码"""
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 20:
            raise ValueError("密码长度必须在 8-20 个字符之间")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("密码必须同时包含字母和数字")
        return v


class ProductStatusCount(BaseModel):
    """商品状态统计项"""
    status: str
    count: int


class CategoryProductCount(BaseModel):
    """分类商品数量统计项"""
    category_id: int
    category_name: str
    product_count: int


class HotProductItem(BaseModel):
    """热门商品项"""
    id: int
    name: str
    hot_score: int
    stock: int
    status: str


class DashboardStatsResponse(BaseModel):
    """Dashboard 统计响应"""
    product_total: int
    on_sale_total: int
    off_sale_total: int
    low_stock_total: int
    out_of_stock_total: int
    category_total: int
    status_distribution: list[ProductStatusCount]
    top_categories: list[CategoryProductCount]
    top_hot_products: list[HotProductItem]


class RecoveryRequestResponse(BaseModel):
    """账号恢复申请响应"""
    id: int
    user_id: int
    username: str
    reason: str
    status: str
    admin_note: str | None = None
    created_at: str
    processed_at: str | None = None

    class Config:
        from_attributes = True


class RecoveryRequestListResponse(BaseModel):
    """账号恢复申请列表响应"""
    total: int
    items: list[RecoveryRequestResponse]


class RecoveryRequestProcessRequest(BaseModel):
    """管理员处理恢复申请"""
    status: str = Field(description="approved/rejected")
    admin_note: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("approved", "rejected"):
            raise ValueError("status 只能是 approved 或 rejected")
        return v
