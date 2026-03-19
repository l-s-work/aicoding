"""
商品路由：商品 CRUD、分类管理
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.api.deps import DatabaseSession, CurrentAdmin, CurrentUser
from app.db.models import Product, ProductCategory, ProductEmbedding
from app.schemas.product_schema import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse,
    CategoryCreate, CategoryResponse
)

router = APIRouter(prefix="/products", tags=["商品"])


# ==================== 分类管理 ====================

@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(category_data: CategoryCreate, db: DatabaseSession, admin: CurrentAdmin):
    """创建商品分类 (仅管理员)"""
    # 验证 category_code 唯一性
    result = await db.execute(
        select(ProductCategory).where(ProductCategory.category_code == category_data.category_code)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"分类编码 {category_data.category_code} 已存在"
        )
    
    # 如果有父级分类，验证其存在性
    if category_data.parent_id:
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.id == category_data.parent_id)
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="父级分类不存在"
            )
    
    category = ProductCategory(**category_data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    
    return category


@router.get("/categories", response_model=list[CategoryResponse])
async def get_categories(
    level: Optional[int] = Query(None, description="筛选层级 (1/2/3)"),
    db: DatabaseSession = None
):
    """获取商品分类列表"""
    query = select(ProductCategory)
    
    if level:
        query = query.where(ProductCategory.level == level)
    
    query = query.order_by(ProductCategory.sort_order, ProductCategory.id)
    
    result = await db.execute(query)
    categories = result.scalars().all()
    
    return categories


# ==================== 商品管理 ====================

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(product_data: ProductCreate, db: DatabaseSession, admin: CurrentAdmin):
    """创建商品 (仅管理员)"""
    # 验证分类存在性
    if product_data.category_id:
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.id == product_data.category_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分类不存在"
            )
    
    product = Product(**product_data.model_dump())
    product.created_at = datetime.utcnow().isoformat()
    
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # TODO: 异步生成 Embedding (后台任务)
    # 这里可以使用 FastAPI 的 BackgroundTasks 来异步生成向量
    
    return product


@router.get("", response_model=ProductListResponse)
async def get_products(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category_ids: Optional[List[int]] = Query(None, description="分类ID列表筛选，支持多个分类，自动包含子分类"),
    status: Optional[str] = Query(None, description="状态筛选 (on_sale/off_sale)"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: DatabaseSession = None
):
    """
    获取商品列表 (分页、筛选、搜索，包含分类信息)
    
    - page: 页码 (从1开始)
    - page_size: 每页数量
    - category_ids: 按分类ID列表筛选（支持多个，自动包含所有子分类）
    - status: 按状态筛选 (on_sale/off_sale)
    - keyword: 关键词搜索 (商品名称)
    
    注意：选择一级或二级分类时，会自动包含其所有子分类的商品
    """
    # 构建查询
    query = select(Product).options(selectinload(Product.category))  # 预加载分类
    
    # 分类筛选（支持级联查询）
    if category_ids:
        # 递归查询所有子孙分类
        all_category_ids = set(category_ids)  # 先加入选中的分类
        
        # 查询所有分类数据（用于构建树形关系）
        cat_result = await db.execute(select(ProductCategory))
        all_categories = cat_result.scalars().all()
        
        # 构建父子关系映射
        category_map = {cat.id: cat for cat in all_categories}
        
        # 递归函数：获取某个分类的所有子孙分类ID
        def get_descendant_ids(parent_id: int) -> set:
            descendants = set()
            for cat in all_categories:
                if cat.parent_id == parent_id:
                    descendants.add(cat.id)
                    # 递归获取子分类的子分类
                    descendants.update(get_descendant_ids(cat.id))
            return descendants
        
        # 对每个选中的分类，查找其所有子孙分类
        for category_id in category_ids:
            all_category_ids.update(get_descendant_ids(category_id))
        
        # 使用完整的分类ID列表查询商品
        query = query.where(Product.category_id.in_(all_category_ids))
    
    if status:
        query = query.where(Product.status == status)
    
    if keyword:
        query = query.where(Product.name.like(f"%{keyword}%"))
    
    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(Product.hot_score.desc(), Product.id.desc())
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    products = result.scalars().all()
    
    return ProductListResponse(total=total, items=products)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: DatabaseSession):
    """获取商品详情（包含完整分类信息）"""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))  # 预加载分类数据
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品不存在"
        )
    
    return product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: DatabaseSession,
    admin: CurrentAdmin
):
    """更新商品信息 (仅管理员)"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品不存在"
        )
    
    # 更新字段 (仅更新提供的字段)
    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.utcnow().isoformat()
    
    await db.commit()
    await db.refresh(product)
    
    # TODO: 如果名称或描述变更，需重新生成 Embedding
    
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, db: DatabaseSession, admin: CurrentAdmin):
    """删除商品 (仅管理员)"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品不存在"
        )
    
    await db.delete(product)
    await db.commit()
