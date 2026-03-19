"""
商品相关 Pydantic Schemas
"""
from pydantic import BaseModel, field_validator
from typing import Optional


class CategoryBase(BaseModel):
    """分类基础模型"""
    category_code: str
    name: str
    parent_id: Optional[int] = None
    level: int
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    """创建分类请求"""
    pass


class CategoryResponse(CategoryBase):
    """分类响应"""
    id: int
    created_at: str
    
    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    """商品基础模型"""
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    category_id: Optional[int] = None
    image_url: Optional[str] = None
    tags: Optional[str] = None  # JSON 字符串
    hot_score: int = 0
    status: str = "on_sale"
    
    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v < 0:
            raise ValueError("价格不能为负数")
        return v
    
    @field_validator("stock")
    @classmethod
    def validate_stock(cls, v: int) -> int:
        if v < 0:
            raise ValueError("库存不能为负数")
        return v


class ProductCreate(ProductBase):
    """创建商品请求"""
    pass


class ProductUpdate(BaseModel):
    """更新商品请求 (所有字段可选)"""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category_id: Optional[int] = None
    image_url: Optional[str] = None
    tags: Optional[str] = None
    hot_score: Optional[int] = None
    status: Optional[str] = None


class ProductResponse(ProductBase):
    """商品响应"""
    id: int
    created_at: str
    updated_at: Optional[str] = None
    category: Optional[CategoryResponse] = None  # 嵌套分类完整信息
    
    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """商品列表响应"""
    total: int
    items: list[ProductResponse]
