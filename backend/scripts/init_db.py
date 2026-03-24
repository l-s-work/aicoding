"""
数据库初始化脚本

能力：
1. 创建表结构；
2. 初始化管理员账户；
3. 初始化三级商品分类；
4. 初始化商品样例（含价格、库存、标签、图片 URL）。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径，保证可导入 app.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal, init_db
from app.db.models import Product, ProductCategory, User
from seed_catalog import CATEGORY_SEEDS, PRODUCT_SEEDS, build_placeholder_image_url

SEED_IMAGE_MAP_FILE = Path(__file__).resolve().with_name("seed_images.json")


def _load_seed_image_map() -> dict[str, str]:
    """
    读取图片映射文件（由 fetch_seed_images.py 生成）。

    返回格式：
    {
      "商品名A": "/uploads/products/xxx.jpg",
      "商品名B": "https://placehold.co/..."
    }
    """
    if not SEED_IMAGE_MAP_FILE.exists():
        return {}

    try:
        payload = json.loads(SEED_IMAGE_MAP_FILE.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return {
            str(name): str(url)
            for name, url in payload.items()
            if isinstance(name, str) and isinstance(url, str) and url.strip()
        }
    except Exception:  # noqa: BLE001
        # 种子映射损坏时兜底，避免阻断初始化流程
        return {}


async def init_admin_user() -> None:
    """创建默认管理员账户"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print("⚠️  管理员账户已存在")
            return

        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            role="admin",
            token_version=1,
        )
        db.add(admin)
        await db.commit()

        print("✅ 管理员账户创建成功")
        print("   用户名: admin")
        print("   密码: admin123")
        print("   ⚠️  请在生产环境中修改默认密码！")


async def init_sample_categories() -> None:
    """创建示例商品分类（三级树形结构）"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count()).select_from(ProductCategory))
        if (result.scalar() or 0) > 0:
            print("⚠️  商品分类已存在")
            return

        code_to_category: dict[str, ProductCategory] = {}
        created_total = 0

        # 按层级写入，确保 parent_id 可引用到前一层
        for level in (1, 2, 3):
            current_level_items = [seed for seed in CATEGORY_SEEDS if seed["level"] == level]

            for seed in current_level_items:
                parent_id = None
                parent_code = seed["parent_code"]
                if parent_code is not None:
                    parent = code_to_category.get(parent_code)
                    if parent is None:
                        raise RuntimeError(f"分类种子配置错误：缺少父级 {parent_code}")
                    parent_id = parent.id

                category = ProductCategory(
                    category_code=seed["category_code"],
                    name=seed["name"],
                    parent_id=parent_id,
                    level=seed["level"],
                    sort_order=seed["sort_order"],
                )
                db.add(category)
                code_to_category[seed["category_code"]] = category
                created_total += 1

            await db.commit()

        level1_count = len([seed for seed in CATEGORY_SEEDS if seed["level"] == 1])
        level2_count = len([seed for seed in CATEGORY_SEEDS if seed["level"] == 2])
        level3_count = len([seed for seed in CATEGORY_SEEDS if seed["level"] == 3])

        print("✅ 示例商品分类创建成功")
        print(f"   一级分类: {level1_count} 个")
        print(f"   二级分类: {level2_count} 个")
        print(f"   三级分类: {level3_count} 个")
        print(f"   总计: {created_total} 个分类")


async def init_sample_products() -> None:
    """创建示例商品（字段完整，优先使用本地图片映射）"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count()).select_from(Product))
        if (result.scalar() or 0) > 0:
            print("⚠️  示例商品已存在")
            return

        # 查询全部分类，建立 category_code -> id 映射
        categories_result = await db.execute(select(ProductCategory))
        categories = categories_result.scalars().all()
        category_code_to_id = {category.category_code: category.id for category in categories}

        image_map = _load_seed_image_map()
        missing_category_count = 0
        created_count = 0

        for seed in PRODUCT_SEEDS:
            category_id = category_code_to_id.get(seed["category_code"])
            if category_id is None:
                missing_category_count += 1
                print(f"⚠️  跳过商品（分类不存在）: {seed['name']} -> {seed['category_code']}")
                continue

            image_url = image_map.get(seed["name"]) or build_placeholder_image_url(seed["name"])
            product = Product(
                name=seed["name"],
                description=seed["description"],
                price=seed["price"],
                stock=seed["stock"],
                category_id=category_id,
                image_url=image_url,
                tags=json.dumps(seed["tags"], ensure_ascii=False),
                hot_score=seed["hot_score"],
                status=seed["status"],
            )
            db.add(product)
            created_count += 1

        await db.commit()

        print("✅ 示例商品创建成功")
        print(f"   成功写入: {created_count} 条")
        print(f"   跳过条数: {missing_category_count} 条")
        print(f"   使用图片映射: {'是' if bool(image_map) else '否（已回退占位图）'}")


async def main() -> None:
    """主函数"""
    print("=" * 50)
    print("🔧 开始初始化数据库...")
    print("=" * 50)

    await init_db()
    await init_admin_user()
    await init_sample_categories()
    await init_sample_products()

    print("=" * 50)
    print("🎉 数据库初始化完成！")
    print("=" * 50)
    print("\n📝 下一步:")
    print("1. 复制 .env.example 为 .env")
    print("2. 配置 OpenAI API Key")
    print("3. （可选）先运行 python scripts\\fetch_seed_images.py 生成商品图片映射")
    print("4. 启动服务: uvicorn app.main:app --reload")
    print("5. 访问: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    asyncio.run(main())
