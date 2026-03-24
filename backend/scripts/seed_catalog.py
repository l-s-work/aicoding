"""
商品初始化种子数据

说明：
- 这里集中维护“分类树 + 商品样例”；
- 初始化数据库脚本与图片抓取脚本共享这份数据，避免多处重复维护。
"""
from __future__ import annotations

from typing import Literal, TypedDict
from urllib.parse import quote


class SeedCategory(TypedDict):
    """分类种子结构"""

    category_code: str
    name: str
    parent_code: str | None
    level: Literal[1, 2, 3]
    sort_order: int


class SeedProduct(TypedDict):
    """商品种子结构"""

    name: str
    description: str
    price: float
    stock: int
    category_code: str
    tags: list[str]
    hot_score: int
    status: Literal["on_sale", "off_sale"]
    image_query: str


# ==================== 分类种子（三级） ====================

CATEGORY_SEEDS: list[SeedCategory] = [
    # 一级分类
    {"category_code": "01", "name": "电子产品", "parent_code": None, "level": 1, "sort_order": 1},
    {"category_code": "02", "name": "服装鞋帽", "parent_code": None, "level": 1, "sort_order": 2},
    {"category_code": "03", "name": "图书音像", "parent_code": None, "level": 1, "sort_order": 3},
    # 二级分类
    {"category_code": "01-01", "name": "手机通讯", "parent_code": "01", "level": 2, "sort_order": 1},
    {"category_code": "01-02", "name": "电脑办公", "parent_code": "01", "level": 2, "sort_order": 2},
    {"category_code": "01-03", "name": "游戏设备", "parent_code": "01", "level": 2, "sort_order": 3},
    {"category_code": "02-01", "name": "男装", "parent_code": "02", "level": 2, "sort_order": 1},
    {"category_code": "02-02", "name": "女装", "parent_code": "02", "level": 2, "sort_order": 2},
    {"category_code": "02-03", "name": "运动鞋服", "parent_code": "02", "level": 2, "sort_order": 3},
    {"category_code": "03-01", "name": "文学小说", "parent_code": "03", "level": 2, "sort_order": 1},
    {"category_code": "03-02", "name": "科技图书", "parent_code": "03", "level": 2, "sort_order": 2},
    # 三级分类（叶子）
    {"category_code": "01-01-01", "name": "5G 手机", "parent_code": "01-01", "level": 3, "sort_order": 1},
    {"category_code": "01-01-02", "name": "游戏手机", "parent_code": "01-01", "level": 3, "sort_order": 2},
    {"category_code": "01-02-01", "name": "笔记本电脑", "parent_code": "01-02", "level": 3, "sort_order": 1},
    {"category_code": "01-02-02", "name": "台式机", "parent_code": "01-02", "level": 3, "sort_order": 2},
    {"category_code": "01-03-01", "name": "游戏主机", "parent_code": "01-03", "level": 3, "sort_order": 1},
    {"category_code": "01-03-02", "name": "游戏手柄", "parent_code": "01-03", "level": 3, "sort_order": 2},
    {"category_code": "02-01-01", "name": "男士 T 恤", "parent_code": "02-01", "level": 3, "sort_order": 1},
    {"category_code": "02-01-02", "name": "男士衬衫", "parent_code": "02-01", "level": 3, "sort_order": 2},
    {"category_code": "02-02-01", "name": "连衣裙", "parent_code": "02-02", "level": 3, "sort_order": 1},
    {"category_code": "02-02-02", "name": "女士上衣", "parent_code": "02-02", "level": 3, "sort_order": 2},
    {"category_code": "02-03-01", "name": "运动鞋", "parent_code": "02-03", "level": 3, "sort_order": 1},
    {"category_code": "02-03-02", "name": "运动套装", "parent_code": "02-03", "level": 3, "sort_order": 2},
    {"category_code": "03-01-01", "name": "经典名著", "parent_code": "03-01", "level": 3, "sort_order": 1},
    {"category_code": "03-01-02", "name": "悬疑推理", "parent_code": "03-01", "level": 3, "sort_order": 2},
    {"category_code": "03-02-01", "name": "编程开发", "parent_code": "03-02", "level": 3, "sort_order": 1},
    {"category_code": "03-02-02", "name": "人工智能", "parent_code": "03-02", "level": 3, "sort_order": 2},
]


# ==================== 商品种子（字段完整） ====================

PRODUCT_SEEDS: list[SeedProduct] = [
    {
        "name": "苹果 iPhone 15 Pro",
        "description": "A17 Pro 芯片与钛金属机身，支持高质量影像创作与日常高性能体验。",
        "price": 7999.00,
        "stock": 50,
        "category_code": "01-01-01",
        "tags": ["手机", "苹果", "5G"],
        "hot_score": 100,
        "status": "on_sale",
        "image_query": "iphone 15 pro smartphone",
    },
    {
        "name": "vivo X100 Pro",
        "description": "旗舰影像手机，适合夜景和人像拍摄，兼顾日常性能与续航。",
        "price": 4999.00,
        "stock": 66,
        "category_code": "01-01-01",
        "tags": ["手机", "vivo", "影像"],
        "hot_score": 91,
        "status": "on_sale",
        "image_query": "vivo smartphone product photo",
    },
    {
        "name": "ROG Phone 8",
        "description": "专注游戏场景的高刷屏手机，强调散热、触控与性能释放。",
        "price": 6999.00,
        "stock": 28,
        "category_code": "01-01-02",
        "tags": ["手机", "游戏", "高性能"],
        "hot_score": 88,
        "status": "on_sale",
        "image_query": "gaming smartphone",
    },
    {
        "name": "红魔 10 Pro",
        "description": "游戏向旗舰机型，支持肩键操控与长时间稳定输出。",
        "price": 5299.00,
        "stock": 36,
        "category_code": "01-01-02",
        "tags": ["手机", "游戏", "电竞"],
        "hot_score": 84,
        "status": "on_sale",
        "image_query": "red gaming phone",
    },
    {
        "name": "MacBook Pro 14 英寸 (M3)",
        "description": "适合开发与创作的高性能笔记本，屏幕素质与续航表现优秀。",
        "price": 14999.00,
        "stock": 30,
        "category_code": "01-02-01",
        "tags": ["笔记本", "苹果", "办公"],
        "hot_score": 92,
        "status": "on_sale",
        "image_query": "macbook pro laptop",
    },
    {
        "name": "ThinkPad X1 Carbon",
        "description": "轻薄商务本，键盘体验与可靠性表现稳定，适合差旅办公。",
        "price": 10999.00,
        "stock": 42,
        "category_code": "01-02-01",
        "tags": ["笔记本", "商务", "办公"],
        "hot_score": 81,
        "status": "on_sale",
        "image_query": "business laptop",
    },
    {
        "name": "惠普暗影精灵台式机",
        "description": "桌面游戏主机，适合 2K 游戏与基础创作工作流。",
        "price": 8299.00,
        "stock": 21,
        "category_code": "01-02-02",
        "tags": ["台式机", "游戏", "电竞"],
        "hot_score": 76,
        "status": "on_sale",
        "image_query": "gaming desktop pc",
    },
    {
        "name": "戴尔成就台式主机",
        "description": "中小企业办公常用台式机，稳定性好，支持多任务并行。",
        "price": 5699.00,
        "stock": 33,
        "category_code": "01-02-02",
        "tags": ["台式机", "办公", "企业"],
        "hot_score": 66,
        "status": "on_sale",
        "image_query": "office desktop computer",
    },
    {
        "name": "索尼 PlayStation 5",
        "description": "次世代游戏主机，支持高帧率与丰富独占游戏生态。",
        "price": 3899.00,
        "stock": 100,
        "category_code": "01-03-01",
        "tags": ["游戏主机", "索尼", "娱乐"],
        "hot_score": 90,
        "status": "on_sale",
        "image_query": "playstation 5 console",
    },
    {
        "name": "任天堂 Switch OLED",
        "description": "便携与主机双模式，适合家庭与轻度玩家。",
        "price": 2299.00,
        "stock": 140,
        "category_code": "01-03-01",
        "tags": ["游戏主机", "任天堂", "便携"],
        "hot_score": 85,
        "status": "on_sale",
        "image_query": "nintendo switch oled",
    },
    {
        "name": "Xbox 无线手柄",
        "description": "多平台兼容手柄，握持与按键反馈均衡，适合长时间游戏。",
        "price": 439.00,
        "stock": 300,
        "category_code": "01-03-02",
        "tags": ["手柄", "Xbox", "外设"],
        "hot_score": 72,
        "status": "on_sale",
        "image_query": "xbox wireless controller",
    },
    {
        "name": "北通阿修罗 2 Pro",
        "description": "支持自定义按键与多种连接方式，适合 PC/主机游戏。",
        "price": 299.00,
        "stock": 220,
        "category_code": "01-03-02",
        "tags": ["手柄", "北通", "外设"],
        "hot_score": 63,
        "status": "on_sale",
        "image_query": "game controller",
    },
    {
        "name": "男士纯棉圆领 T 恤",
        "description": "基础百搭款，面料亲肤，适合春夏日常穿搭。",
        "price": 99.00,
        "stock": 260,
        "category_code": "02-01-01",
        "tags": ["男装", "T恤", "纯棉"],
        "hot_score": 70,
        "status": "on_sale",
        "image_query": "men cotton t shirt",
    },
    {
        "name": "男士免烫商务衬衫",
        "description": "版型利落，易打理，适用于通勤与商务场景。",
        "price": 179.00,
        "stock": 180,
        "category_code": "02-01-02",
        "tags": ["男装", "衬衫", "商务"],
        "hot_score": 64,
        "status": "on_sale",
        "image_query": "men business shirt",
    },
    {
        "name": "法式轻盈连衣裙",
        "description": "简洁优雅的日常连衣裙，适合通勤与约会场景。",
        "price": 259.00,
        "stock": 160,
        "category_code": "02-02-01",
        "tags": ["女装", "连衣裙", "通勤"],
        "hot_score": 73,
        "status": "on_sale",
        "image_query": "women dress fashion",
    },
    {
        "name": "女士雪纺上衣",
        "description": "轻薄透气，版型宽松，适合搭配半裙或牛仔裤。",
        "price": 139.00,
        "stock": 190,
        "category_code": "02-02-02",
        "tags": ["女装", "上衣", "雪纺"],
        "hot_score": 61,
        "status": "on_sale",
        "image_query": "women blouse",
    },
    {
        "name": "Nike Pegasus 41 跑鞋",
        "description": "缓震与回弹表现均衡，适合日常慢跑与轻量训练。",
        "price": 899.00,
        "stock": 120,
        "category_code": "02-03-01",
        "tags": ["运动鞋", "跑鞋", "训练"],
        "hot_score": 82,
        "status": "on_sale",
        "image_query": "running shoes",
    },
    {
        "name": "安踏 C202 竞速跑鞋",
        "description": "主打轻量化与推进感，适合进阶跑步训练。",
        "price": 699.00,
        "stock": 98,
        "category_code": "02-03-01",
        "tags": ["运动鞋", "安踏", "竞速"],
        "hot_score": 79,
        "status": "on_sale",
        "image_query": "sports running shoes",
    },
    {
        "name": "阿迪达斯运动套装",
        "description": "适合健身与通勤，面料舒适，易于日常打理。",
        "price": 499.00,
        "stock": 88,
        "category_code": "02-03-02",
        "tags": ["运动套装", "阿迪达斯", "健身"],
        "hot_score": 68,
        "status": "on_sale",
        "image_query": "sportswear tracksuit",
    },
    {
        "name": "女士瑜伽训练套装",
        "description": "高弹透气，适配瑜伽与低强度有氧训练。",
        "price": 359.00,
        "stock": 95,
        "category_code": "02-03-02",
        "tags": ["运动套装", "瑜伽", "女款"],
        "hot_score": 67,
        "status": "on_sale",
        "image_query": "women yoga outfit",
    },
    {
        "name": "《活着》余华",
        "description": "经典中文文学作品，适合收藏与阅读分享。",
        "price": 39.90,
        "stock": 500,
        "category_code": "03-01-01",
        "tags": ["文学", "经典名著", "中文"],
        "hot_score": 86,
        "status": "on_sale",
        "image_query": "chinese novel book cover",
    },
    {
        "name": "《百年孤独》加西亚·马尔克斯",
        "description": "魔幻现实主义代表作，适合文学爱好者深度阅读。",
        "price": 59.00,
        "stock": 320,
        "category_code": "03-01-01",
        "tags": ["文学", "名著", "收藏"],
        "hot_score": 78,
        "status": "on_sale",
        "image_query": "classic novel book",
    },
    {
        "name": "《白夜行》东野圭吾",
        "description": "高口碑悬疑推理小说，剧情紧凑，阅读沉浸感强。",
        "price": 46.00,
        "stock": 420,
        "category_code": "03-01-02",
        "tags": ["推理", "悬疑", "东野圭吾"],
        "hot_score": 83,
        "status": "on_sale",
        "image_query": "mystery novel book",
    },
    {
        "name": "《长夜难明》紫金陈",
        "description": "现实题材悬疑作品，叙事节奏明快。",
        "price": 42.00,
        "stock": 300,
        "category_code": "03-01-02",
        "tags": ["悬疑", "推理", "国产小说"],
        "hot_score": 74,
        "status": "on_sale",
        "image_query": "detective novel cover",
    },
    {
        "name": "《Python 编程：从入门到实践》",
        "description": "覆盖 Python 基础到项目实践，适合编程初学者。",
        "price": 89.00,
        "stock": 260,
        "category_code": "03-02-01",
        "tags": ["编程", "Python", "入门"],
        "hot_score": 87,
        "status": "on_sale",
        "image_query": "python programming book",
    },
    {
        "name": "《深入理解计算机系统》",
        "description": "计算机系统方向经典教材，适合进阶开发者。",
        "price": 128.00,
        "stock": 140,
        "category_code": "03-02-01",
        "tags": ["编程", "计算机系统", "进阶"],
        "hot_score": 80,
        "status": "on_sale",
        "image_query": "computer science book",
    },
    {
        "name": "《动手学深度学习》",
        "description": "结合代码示例讲解深度学习核心概念与实战。",
        "price": 99.00,
        "stock": 200,
        "category_code": "03-02-02",
        "tags": ["人工智能", "深度学习", "实战"],
        "hot_score": 89,
        "status": "on_sale",
        "image_query": "deep learning book",
    },
    {
        "name": "《机器学习实战》",
        "description": "通过案例讲解常见机器学习算法与工程化思路。",
        "price": 79.00,
        "stock": 180,
        "category_code": "03-02-02",
        "tags": ["人工智能", "机器学习", "算法"],
        "hot_score": 77,
        "status": "off_sale",
        "image_query": "machine learning book",
    },
]


def build_placeholder_image_url(product_name: str) -> str:
    """
    兜底占位图 URL（当本地无图或图片抓取失败时使用）。
    """
    return f"https://placehold.co/800x800?text={quote(product_name[:20])}"
