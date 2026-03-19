"""
数据库初始化脚本
创建管理员账户和示例商品数据
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import User, ProductCategory, Product
from app.core.security import hash_password


async def init_admin_user():
    """创建默认管理员账户"""
    async with AsyncSessionLocal() as db:
        # 检查是否已存在管理员
        result = await db.execute(
            select(User).where(User.username == "admin")
        )
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            print("⚠️  管理员账户已存在")
            return
        
        # 创建管理员
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("admin123"),  # 默认密码
            role="admin",
            token_version=1,
        )
        
        db.add(admin)
        await db.commit()
        
        print("✅ 管理员账户创建成功")
        print("   用户名: admin")
        print("   密码: admin123")
        print("   ⚠️  请在生产环境中修改默认密码！")


async def init_sample_categories():
    """创建示例商品分类（三级树形结构）"""
    async with AsyncSessionLocal() as db:
        # 检查是否已有分类
        result = await db.execute(select(ProductCategory))
        if result.scalar_one_or_none():
            print("⚠️  商品分类已存在")
            return
        
        # ===== 第一步：创建一级分类 =====
        level1_categories = [
            {"category_code": "01", "name": "电子产品", "parent_id": None, "level": 1, "sort_order": 1},
            {"category_code": "02", "name": "服装鞋帽", "parent_id": None, "level": 1, "sort_order": 2},
            {"category_code": "03", "name": "图书音像", "parent_id": None, "level": 1, "sort_order": 3},
        ]
        
        # 存储一级分类对象，用于后续建立父子关系（使用 category_code 作为 key）
        level1_map = {}
        for cat_data in level1_categories:
            category = ProductCategory(**cat_data)
            db.add(category)
            level1_map[cat_data["category_code"]] = category
        
        await db.commit()  # 先提交以获取一级分类的 ID
        
        # ===== 第二步：创建二级分类 =====
        level2_categories = [
            # 电子产品 -> 二级分类
            {"category_code": "01-01", "name": "手机通讯", "parent_id": level1_map["01"].id, "level": 2, "sort_order": 1},
            {"category_code": "01-02", "name": "电脑办公", "parent_id": level1_map["01"].id, "level": 2, "sort_order": 2},
            {"category_code": "01-03", "name": "游戏设备", "parent_id": level1_map["01"].id, "level": 2, "sort_order": 3},
            # 服装鞋帽 -> 二级分类
            {"category_code": "02-01", "name": "男装", "parent_id": level1_map["02"].id, "level": 2, "sort_order": 1},
            {"category_code": "02-02", "name": "女装", "parent_id": level1_map["02"].id, "level": 2, "sort_order": 2},
            {"category_code": "02-03", "name": "运动鞋服", "parent_id": level1_map["02"].id, "level": 2, "sort_order": 3},
            # 图书音像 -> 二级分类
            {"category_code": "03-01", "name": "文学小说", "parent_id": level1_map["03"].id, "level": 2, "sort_order": 1},
            {"category_code": "03-02", "name": "科技图书", "parent_id": level1_map["03"].id, "level": 2, "sort_order": 2},
        ]
        
        level2_map = {}
        for cat_data in level2_categories:
            category = ProductCategory(**cat_data)
            db.add(category)
            level2_map[cat_data["category_code"]] = category
        
        await db.commit()  # 提交二级分类
        
        # ===== 第三步：创建三级分类（叶子节点） =====
        level3_categories = [
            # 手机通讯 -> 三级
            {"category_code": "01-01-01", "name": "5G 手机", "parent_id": level2_map["01-01"].id, "level": 3, "sort_order": 1},
            {"category_code": "01-01-02", "name": "游戏手机", "parent_id": level2_map["01-01"].id, "level": 3, "sort_order": 2},
            # 电脑办公 -> 三级
            {"category_code": "01-02-01", "name": "笔记本电脑", "parent_id": level2_map["01-02"].id, "level": 3, "sort_order": 1},
            {"category_code": "01-02-02", "name": "台式机", "parent_id": level2_map["01-02"].id, "level": 3, "sort_order": 2},
            # 游戏设备 -> 三级
            {"category_code": "01-03-01", "name": "游戏主机", "parent_id": level2_map["01-03"].id, "level": 3, "sort_order": 1},
            {"category_code": "01-03-02", "name": "游戏手柄", "parent_id": level2_map["01-03"].id, "level": 3, "sort_order": 2},
            # 男装 -> 三级
            {"category_code": "02-01-01", "name": "男士 T 恤", "parent_id": level2_map["02-01"].id, "level": 3, "sort_order": 1},
            {"category_code": "02-01-02", "name": "男士衬衫", "parent_id": level2_map["02-01"].id, "level": 3, "sort_order": 2},
            # 女装 -> 三级
            {"category_code": "02-02-01", "name": "连衣裙", "parent_id": level2_map["02-02"].id, "level": 3, "sort_order": 1},
            {"category_code": "02-02-02", "name": "女士上衣", "parent_id": level2_map["02-02"].id, "level": 3, "sort_order": 2},
            # 运动鞋服 -> 三级
            {"category_code": "02-03-01", "name": "运动鞋", "parent_id": level2_map["02-03"].id, "level": 3, "sort_order": 1},
            {"category_code": "02-03-02", "name": "运动套装", "parent_id": level2_map["02-03"].id, "level": 3, "sort_order": 2},
            # 文学小说 -> 三级
            {"category_code": "03-01-01", "name": "经典名著", "parent_id": level2_map["03-01"].id, "level": 3, "sort_order": 1},
            {"category_code": "03-01-02", "name": "悬疑推理", "parent_id": level2_map["03-01"].id, "level": 3, "sort_order": 2},
            # 科技图书 -> 三级
            {"category_code": "03-02-01", "name": "编程开发", "parent_id": level2_map["03-02"].id, "level": 3, "sort_order": 1},
            {"category_code": "03-02-02", "name": "人工智能", "parent_id": level2_map["03-02"].id, "level": 3, "sort_order": 2},
        ]
        
        for cat_data in level3_categories:
            category = ProductCategory(**cat_data)
            db.add(category)
        
        await db.commit()
        
        print("✅ 示例商品分类创建成功")
        print(f"   一级分类: {len(level1_categories)} 个")
        print(f"   二级分类: {len(level2_categories)} 个")
        print(f"   三级分类: {len(level3_categories)} 个")
        print(f"   总计: {len(level1_categories) + len(level2_categories) + len(level3_categories)} 个分类")


async def init_sample_products():
    """创建示例商品（关联到三级分类）"""
    async with AsyncSessionLocal() as db:
        # 检查是否已有商品
        result = await db.execute(select(Product))
        if result.scalar_one_or_none():
            print("⚠️  示例商品已存在")
            return
        
        # 获取三级分类 ID（使用 category_code 查询）
        # 5G 手机分类
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.category_code == "01-01-01")
        )
        phone_5g_cat = result.scalar_one_or_none()
        
        # 笔记本电脑分类
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.category_code == "01-02-01")
        )
        laptop_cat = result.scalar_one_or_none()
        
        # 游戏主机分类
        result = await db.execute(
            select(ProductCategory).where(ProductCategory.category_code == "01-03-01")
        )
        console_cat = result.scalar_one_or_none()
        
        # 创建示例商品（关联到三级分类）
        products = [
            {
                "name": "苹果 iPhone 15 Pro",
                "description": "强大的 A17 Pro 芯片，钛金属设计，专业级摄像系统",
                "price": 7999.00,
                "stock": 50,
                "category_id": phone_5g_cat.id if phone_5g_cat else None,
                "tags": '["手机", "苹果", "5G"]',
                "hot_score": 100,
                "status": "on_sale",
            },
            {
                "name": "小米 14 Ultra",
                "description": "徕卡光学镜头，骁龙 8 Gen 3，专业影像旗舰",
                "price": 5999.00,
                "stock": 80,
                "category_id": phone_5g_cat.id if phone_5g_cat else None,
                "tags": '["手机", "小米", "5G", "拍照"]',
                "hot_score": 90,
                "status": "on_sale",
            },
            {
                "name": "华为 Mate 60 Pro",
                "description": "卫星通信，昆仑玻璃，鸿蒙 4.0",
                "price": 6999.00,
                "stock": 60,
                "category_id": phone_5g_cat.id if phone_5g_cat else None,
                "tags": '["手机", "华为", "5G"]',
                "hot_score": 95,
                "status": "on_sale",
            },
            {
                "name": "MacBook Pro 14 英寸 (M3)",
                "description": "Apple M3 芯片，14.2 英寸 Liquid Retina XDR 显示屏",
                "price": 14999.00,
                "stock": 30,
                "category_id": laptop_cat.id if laptop_cat else None,
                "tags": '["笔记本", "苹果", "办公"]',
                "hot_score": 85,
                "status": "on_sale",
            },
            {
                "name": "索尼 PlayStation 5",
                "description": "次世代游戏主机，超高速 SSD，沉浸式游戏体验",
                "price": 3899.00,
                "stock": 100,
                "category_id": console_cat.id if console_cat else None,
                "tags": '["游戏", "主机", "娱乐"]',
                "hot_score": 80,
                "status": "on_sale",
            },
        ]
        
        for product_data in products:
            product = Product(**product_data)
            db.add(product)
        
        await db.commit()
        print("✅ 示例商品创建成功（已关联到三级分类）")


async def main():
    """主函数"""
    print("=" * 50)
    print("🔧 开始初始化数据库...")
    print("=" * 50)
    
    # 1. 创建表结构
    await init_db()
    
    # 2. 初始化管理员
    await init_admin_user()
    
    # 3. 初始化分类
    await init_sample_categories()
    
    # 4. 初始化商品
    await init_sample_products()
    
    print("=" * 50)
    print("🎉 数据库初始化完成！")
    print("=" * 50)
    print("\n📝 下一步:")
    print("1. 复制 .env.example 为 .env")
    print("2. 配置 OpenAI API Key")
    print("3. 运行: uvicorn app.main:app --reload")
    print("4. 访问: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    asyncio.run(main())
