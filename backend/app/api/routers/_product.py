"""
商品路由：商品 CRUD、分类管理
"""
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Query, UploadFile, File
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import DatabaseSession, CurrentAdmin
from app.db.models import Product, ProductCategory
from app.schemas.product_schema import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse,
    CategoryCreate, CategoryResponse, CategoryTreeResponse
)

router = APIRouter(prefix="/products", tags=["商品"])
PRODUCT_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "products"


# ==================== 分类管理 ====================

async def _generate_category_code(
    db: DatabaseSession,
    parent_id: Optional[int],
    parent_code: Optional[str],
    level: int,
) -> str:
    """
    生成分类业务编码（两位一段）
    - 一级: 01, 02, ...
    - 二级: 01-01, 01-02, ...
    - 三级: 01-01-01, 01-01-02, ...
    """
    if parent_id is None:
        stmt = select(ProductCategory.category_code).where(
            ProductCategory.parent_id.is_(None),
            ProductCategory.level == 1
        )
    else:
        stmt = select(ProductCategory.category_code).where(
            ProductCategory.parent_id == parent_id,
            ProductCategory.level == level
        )

    result = await db.execute(stmt)
    sibling_codes = [row[0] for row in result.all()]

    max_segment = 0
    expected_parts = level
    for code in sibling_codes:
        parts = code.split("-")
        if len(parts) != expected_parts:
            continue
        if not all(part.isdigit() for part in parts):
            continue
        max_segment = max(max_segment, int(parts[-1]))

    next_segment = max_segment + 1
    if next_segment > 99:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同级分类数量已达上限（99）"
        )

    segment_code = f"{next_segment:02d}"
    if parent_code is None:
        return segment_code
    return f"{parent_code}-{segment_code}"


def _serialize_category_node(category: ProductCategory) -> dict:
    """将 ORM 分类对象序列化为树节点字典"""
    return {
        "id": category.id,
        "category_code": category.category_code,
        "name": category.name,
        "parent_id": category.parent_id,
        "level": category.level,
        "sort_order": category.sort_order,
        "created_at": category.created_at,
        "children": [],
    }


def _build_tree_from_roots(
    category_by_parent: dict[Optional[int], list[ProductCategory]],
    root_parent_id: Optional[int],
) -> list[dict]:
    """从指定父级 ID 开始递归构建分类树"""
    nodes: list[dict] = []
    for cat in category_by_parent.get(root_parent_id, []):
        node = _serialize_category_node(cat)
        node["children"] = _build_tree_from_roots(category_by_parent, cat.id)
        nodes.append(node)
    return nodes

@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(category_data: CategoryCreate, db: DatabaseSession, admin: CurrentAdmin):
    """
    创建商品分类 (仅管理员)

    前端只需传 name + parent_id(+ sort_order)，后端自动：
    1. 判定 level
    2. 生成 category_code
    """
    # 根据父级分类推导层级
    parent = None
    if category_data.parent_id is not None:
        parent_result = await db.execute(
            select(ProductCategory).where(ProductCategory.id == category_data.parent_id)
        )
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="父级分类不存在"
            )

    level = 1 if parent is None else parent.level + 1
    if level > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最大仅支持三级分类"
        )
    parent_code = None if parent is None else parent.category_code

    # 并发场景下可能发生 category_code 唯一键冲突，自动重试一次
    for attempt in range(2):
        try:
            await db.execute(text("BEGIN IMMEDIATE"))
            generated_code = await _generate_category_code(
                db=db,
                parent_id=category_data.parent_id,
                parent_code=parent_code,
                level=level,
            )

            category = ProductCategory(
                category_code=generated_code,
                name=category_data.name,
                parent_id=category_data.parent_id,
                level=level,
                sort_order=category_data.sort_order,
            )
            db.add(category)
            await db.commit()
            await db.refresh(category)
            return category
        except HTTPException:
            await db.rollback()
            raise
        except IntegrityError:
            await db.rollback()
            if attempt == 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="分类创建冲突，请重试"
                )
        except Exception as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建分类失败: {str(exc)}"
            ) from exc


@router.get("/categories", response_model=list[CategoryTreeResponse])
async def get_categories(
    level: Optional[int] = Query(None, ge=1, le=3, description="按层级筛选 (1/2/3)"),
    category_id: Optional[int] = Query(None, description="按分类查询其子分类"),
    include_self: bool = Query(False, description="按分类查询时是否包含该分类本身"),
    db: DatabaseSession = None
):
    """
    获取商品分类（支持树形与筛选）

    - 默认不传参数：返回完整分类树（一级 -> 二级 -> 三级）
    - 传 category_id：返回该分类下的子分类树（可选 include_self）
    - 传 level：返回指定层级分类（若同时传 category_id，则在该子树范围内筛选）
    """
    result = await db.execute(
        select(ProductCategory).order_by(ProductCategory.sort_order, ProductCategory.id)
    )
    categories = result.scalars().all()

    # 构建 parent_id -> children 映射，便于树形组装
    category_by_parent: dict[Optional[int], list[ProductCategory]] = {}
    category_by_id: dict[int, ProductCategory] = {}
    for cat in categories:
        category_by_id[cat.id] = cat
        category_by_parent.setdefault(cat.parent_id, []).append(cat)

    # 默认根节点集合：一级分类（parent_id=None）
    root_parent_id: Optional[int] = None
    root_category_ids: Optional[list[int]] = None

    if category_id is not None:
        target = category_by_id.get(category_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分类不存在"
            )
        if include_self:
            root_category_ids = [target.id]
        else:
            root_category_ids = [cat.id for cat in category_by_parent.get(target.id, [])]

    # level 筛选：返回当前范围内指定层级的节点（children 为空）
    if level is not None:
        if root_category_ids is None:
            filtered = [cat for cat in categories if cat.level == level]
        else:
            descendants: set[int] = set(root_category_ids)
            stack = list(root_category_ids)
            while stack:
                current_id = stack.pop()
                for child in category_by_parent.get(current_id, []):
                    if child.id not in descendants:
                        descendants.add(child.id)
                        stack.append(child.id)
            filtered = [cat for cat in categories if cat.id in descendants and cat.level == level]

        return [
            {
                **_serialize_category_node(cat),
                "children": [],
            }
            for cat in filtered
        ]

    # 非 level 筛选：返回树结构
    if root_category_ids is None:
        return _build_tree_from_roots(category_by_parent, root_parent_id)

    tree_nodes: list[dict] = []
    for root_id in root_category_ids:
        root_cat = category_by_id.get(root_id)
        if not root_cat:
            continue
        node = _serialize_category_node(root_cat)
        node["children"] = _build_tree_from_roots(category_by_parent, root_cat.id)
        tree_nodes.append(node)
    return tree_nodes


# ==================== 商品管理 ====================

async def _get_product_with_category(db: DatabaseSession, product_id: int) -> Product:
    """
    按 ID 查询商品并预加载分类，避免响应序列化阶段触发异步懒加载。
    """
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品不存在"
        )
    return product

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(product_data: ProductCreate, db: DatabaseSession, admin: CurrentAdmin):
    """创建商品 (仅管理员)"""
    # 验证分类存在性：商品必须挂在三级分类节点（叶子节点）
    if product_data.category_id:
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.id == product_data.category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分类不存在"
            )
        if category.level != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="创建商品时必须选择三级分类"
            )
    
    product = Product(**product_data.model_dump())
    product.created_at = datetime.utcnow().isoformat()
    
    db.add(product)
    await db.commit()
    # 创建后重新查询并预加载 category，避免 FastAPI 响应校验时触发懒加载报错
    product_with_category = await _get_product_with_category(db, product.id)
    
    # TODO: 异步生成 Embedding (后台任务)
    # 这里可以使用 FastAPI 的 BackgroundTasks 来异步生成向量
    
    return product_with_category


@router.post("/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    admin: CurrentAdmin = None,
):
    """
    商品图片上传（单图）

    - 仅允许图片 MIME 类型
    - 限制大小 5MB，避免上传超大文件影响单机稳定性
    - 文件保存到 backend/uploads/products
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持图片文件上传"
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件不能为空"
        )
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="图片大小不能超过 5MB"
        )

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        # 若前端文件名无扩展名，则根据 content_type 兜底
        mime_suffix_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        suffix = mime_suffix_map.get(file.content_type, ".jpg")

    PRODUCT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    save_path = PRODUCT_UPLOAD_DIR / filename
    save_path.write_bytes(content)

    return {"url": f"/uploads/products/{filename}"}


@router.get("", response_model=ProductListResponse)
async def get_products(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category_id: Optional[int] = Query(None, description="单个分类ID筛选，自动包含子分类"),
    category_ids: Optional[List[int]] = Query(None, description="分类ID列表筛选，支持多个分类，自动包含子分类"),
    level: Optional[int] = Query(None, ge=1, le=3, description="按分类层级筛选 (1/2/3)"),
    status: Optional[str] = Query(None, description="状态筛选 (on_sale/off_sale)"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: DatabaseSession = None
):
    """
    获取商品列表 (分页、筛选、搜索，包含分类信息)
    
    - page: 页码 (从1开始)
    - page_size: 每页数量
    - category_id: 按单个分类ID筛选（自动包含所有子分类）
    - category_ids: 按分类ID列表筛选（支持多个，自动包含所有子分类）
    - level: 按分类层级筛选（1/2/3）
    - status: 按状态筛选 (on_sale/off_sale)
    - keyword: 关键词搜索 (商品名称)
    
    注意：选择一级或二级分类时，会自动包含其所有子分类的商品
    """
    # 构建查询
    query = select(Product).options(selectinload(Product.category))  # 预加载分类
    
    # 分类筛选（支持级联查询）
    selected_category_ids = set(category_ids or [])
    if category_id is not None:
        selected_category_ids.add(category_id)

    if selected_category_ids:
        # 递归查询所有子孙分类
        all_category_ids = set(selected_category_ids)  # 先加入选中的分类
        
        # 查询所有分类数据（用于构建树形关系）
        cat_result = await db.execute(select(ProductCategory))
        all_categories = cat_result.scalars().all()
        all_existing_ids = {cat.id for cat in all_categories}
        missing_ids = [selected_id for selected_id in selected_category_ids if selected_id not in all_existing_ids]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"分类不存在: {missing_ids[0]}"
            )
        
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
        for selected_id in selected_category_ids:
            all_category_ids.update(get_descendant_ids(selected_id))
        
        # 使用完整的分类ID列表查询商品
        query = query.where(Product.category_id.in_(all_category_ids))

    # 按分类层级筛选（需要 join 分类表）
    if level is not None:
        query = query.join(ProductCategory, Product.category_id == ProductCategory.id)
        query = query.where(ProductCategory.level == level)
    
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
    
    # 若更新了分类，强制校验：商品必须挂在三级分类节点（叶子节点）
    if product_data.category_id is not None:
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.id == product_data.category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分类不存在"
            )
        if category.level != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="商品分类必须为三级分类（叶子节点）"
            )

    # 更新字段 (仅更新提供的字段)
    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.utcnow().isoformat()
    
    await db.commit()
    # 更新后重新查询并预加载 category，避免响应阶段触发异步懒加载
    product_with_category = await _get_product_with_category(db, product.id)
    
    # TODO: 如果名称或描述变更，需重新生成 Embedding
    
    return product_with_category


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
