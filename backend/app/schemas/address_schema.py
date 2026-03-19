"""
收货地址相关 Pydantic Schemas
"""
from pydantic import BaseModel, field_validator
import re


class AddressBase(BaseModel):
    """地址基础模型"""
    receiver_name: str
    phone: str
    province: str
    city: str
    district: str
    detail_address: str
    is_default: int = 0
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # 简单的手机号校验
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class AddressCreate(AddressBase):
    """创建地址请求"""
    pass


class AddressUpdate(BaseModel):
    """更新地址请求 (所有字段可选)"""
    receiver_name: str | None = None
    phone: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    detail_address: str | None = None
    is_default: int | None = None


class AddressResponse(AddressBase):
    """地址响应"""
    id: int
    user_id: int
    created_at: str
    
    class Config:
        from_attributes = True
