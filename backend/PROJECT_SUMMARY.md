# 后端项目说明

## 🎉 项目已完成

后端项目基于 **FastAPI + SQLAlchemy 2.0 + OpenAI** 已全部搭建完成。

## 📁 项目结构

```
backend/
├── app/
│   ├── core/                    # 核心配置模块
│   │   ├── config.py           # 环境变量加载 (Pydantic Settings)
│   │   └── security.py         # JWT Token 生成/验证、密码哈希
│   ├── db/                      # 数据库层
│   │   ├── database.py         # SQLite 异步连接配置 (WAL 模式)
│   │   └── models.py           # SQLAlchemy ORM 模型 (9张表)
│   ├── schemas/                 # Pydantic 数据模型
│   │   ├── auth_schema.py      # 认证相关 DTO
│   │   ├── product_schema.py   # 商品相关 DTO
│   │   ├── order_schema.py     # 订单相关 DTO
│   │   ├── address_schema.py   # 地址相关 DTO
│   │   └── chat_schema.py      # AI 对话相关 DTO
│   ├── api/
│   │   ├── deps.py             # 依赖注入 (获取当前用户、数据库会话等)
│   │   └── routers/            # API 路由模块
│   │       ├── _auth.py        # 认证路由 (注册、登录、刷新Token、登出)
│   │       ├── _product.py     # 商品路由 (CRUD、分类管理)
│   │       ├── _order.py       # 订单路由 (创建、查询、支付、取消)
│   │       ├── _address.py     # 收货地址路由 (CRUD、设为默认)
│   │       └── _ai.py          # AI 对话路由 (流式对话、历史记录)
│   ├── services/                # 业务逻辑层
│   │   ├── order_service.py    # 订单服务 (原子库存扣减、快照保存)
│   │   └── ai_service.py       # AI 服务 (OpenAI 集成、向量计算)
│   └── main.py                  # FastAPI 应用入口
├── scripts/
│   ├── init_db.py              # 数据库初始化脚本
│   └── dev_server.py           # 开发服务器启动脚本
├── requirements.txt             # Python 依赖
├── .env.example                # 环境变量模板
├── .env                        # 环境变量配置 (已创建)
├── .gitignore                  # Git 忽略文件
├── README.md                   # 项目说明
└── QUICKSTART.md               # 快速开始指南
```

## ✨ 核心特性实现

### 1. 认证系统 ✅

- **双 Token 机制**: Access Token (2小时) + Refresh Token (7天)
- **Token 版本控制**: 支持强制踢出所有设备
- **防暴力破解**: 5次失败锁定10分钟
- **角色权限**: 区分普通用户和管理员

### 2. 商品管理 ✅

- **三级分类**: 支持树形分类结构
- **CRUD 操作**: 完整的增删改查
- **分页搜索**: 支持关键词搜索和条件筛选
- **向量化**: 支持商品 Embedding 生成

### 3. 订单系统 ✅

- **原子库存扣减**: 使用 SQLite 条件 UPDATE 防超卖
- **快照设计**:
  - 地址快照 (receiver_info JSON)
  - 价格快照 (buy_price 字段)
- **状态流转**: pending → paid → shipped → completed
- **库存回滚**: 取消订单自动归还库存

### 4. AI 智能推荐 ✅

- **OpenAI 集成**: 使用 gpt-4o-mini 模型
- **向量搜索**: Numpy 计算余弦相似度
- **流式输出**: SSE (Server-Sent Events) 实现打字机效果
- **对话历史**: 保存完整对话记录

### 5. 收货地址 ✅

- **多地址管理**: 最多5个地址
- **默认地址**: 唯一默认地址逻辑
- **地址快照**: 订单创建时硬拷贝地址信息

## 🚀 快速启动

### 第一步：安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 第二步：配置 OpenAI API Key

编辑 `.env` 文件，填入你的 OpenAI API Key：

```env
OPENAI_API_KEY=sk-your-api-key-here
```

### 第三步：初始化数据库

```bash
python scripts/init_db.py
```

这将创建：

- 管理员账户：admin / admin123
- 示例商品分类
- 5个示例商品

### 第四步：启动服务

```bash
python scripts/dev_server.py
```

或者：

```bash
uvicorn app.main:app --reload
```

### 第五步：访问 API 文档

打开浏览器访问：http://localhost:8000/docs

## 📋 数据库表结构

1. **users** - 用户表 (含 token_version 防踢出)
2. **refresh_tokens** - Refresh Token 记录表
3. **product_categories** - 商品分类表 (三级树形)
4. **products** - 商品主表
5. **product_embeddings** - 商品向量表
6. **user_addresses** - 收货地址表
7. **orders** - 订单主表 (含地址快照)
8. **order_items** - 订单明细表 (含价格快照)
9. **chat_messages** - AI 对话记录表

## 🔑 API 路由概览

### 认证相关 (/auth)

- POST /auth/register - 用户注册
- POST /auth/login - 用户登录
- POST /auth/refresh - 刷新 Access Token
- POST /auth/logout - 登出当前设备
- POST /auth/logout-all - 退出所有设备
- GET /auth/me - 获取当前用户信息

### 商品相关 (/products)

- GET /products - 获取商品列表 (分页、搜索)
- GET /products/{id} - 获取商品详情
- POST /products - 创建商品 (管理员)
- PUT /products/{id} - 更新商品 (管理员)
- DELETE /products/{id} - 删除商品 (管理员)
- GET /products/categories - 获取分类列表
- POST /products/categories - 创建分类 (管理员)

### 订单相关 (/orders)

- POST /orders - 创建订单
- GET /orders - 获取我的订单列表
- GET /orders/{id} - 获取订单详情
- POST /orders/{id}/pay - 支付订单 (假支付)
- POST /orders/{id}/cancel - 取消订单
- GET /orders/admin/all - 管理员查看所有订单
- PUT /orders/admin/{id}/status - 管理员更新订单状态

### 地址相关 (/addresses)

- GET /addresses - 获取我的地址列表
- GET /addresses/{id} - 获取地址详情
- POST /addresses - 创建地址
- PUT /addresses/{id} - 更新地址
- DELETE /addresses/{id} - 删除地址
- POST /addresses/{id}/set-default - 设为默认地址

### AI 对话相关 (/ai)

- POST /ai/chat/stream - 流式对话 (SSE)
- POST /ai/chat - 非流式对话
- GET /ai/history - 获取对话历史
- DELETE /ai/history - 清空对话历史
- POST /ai/products/{id}/sync-embedding - 同步商品向量

## 🎯 核心设计亮点

### 1. 原子库存扣减 (防超卖)

```python
# 使用条件 UPDATE，库存不足时影响 0 行
UPDATE products
SET stock = stock - :quantity
WHERE id = :product_id AND stock >= :quantity

# 检查 rowcount，为 0 则回滚事务
if result.rowcount == 0:
    await db.rollback()
    raise HTTPException(400, "库存不足")
```

### 2. 快照设计 (防数据变更影响历史)

订单创建时硬拷贝：

- **地址快照**: 存入 `orders.receiver_info` (JSON)
- **价格快照**: 存入 `order_items.buy_price` (Float)

### 3. 本地向量计算 (轻量化)

```python
# 使用 Numpy 计算余弦相似度，无需向量数据库
similarity = np.dot(query_vec, product_vec) / (
    np.linalg.norm(query_vec) * np.linalg.norm(product_vec)
)
```

### 4. SSE 流式输出

```python
async def event_generator():
    async for chunk in openai_stream:
        yield f"data: {json.dumps(chunk)}\n\n"

return StreamingResponse(
    event_generator(),
    media_type="text/event-stream"
)
```

## 📦 依赖说明

| 依赖       | 版本    | 用途            |
| ---------- | ------- | --------------- |
| fastapi    | 0.115.0 | Web 框架        |
| sqlalchemy | 2.0.35  | ORM (异步模式)  |
| aiosqlite  | 0.20.0  | SQLite 异步驱动 |
| pydantic   | 2.9.2   | 数据验证        |
| bcrypt     | 4.0.1   | 密码哈希加密    |
| pyjwt      | 2.9.0   | JWT Token       |
| openai     | 1.51.2  | OpenAI API      |
| numpy      | 2.1.3   | 向量计算        |

## ⚠️ 重要提示

1. **生产环境**请修改 `.env` 中的 `JWT_SECRET_KEY`
2. **OpenAI API Key** 需要自行申请并配置
3. 默认管理员密码 **admin123** 请在生产环境中修改
4. SQLite 适合小型项目，大规模请换用 PostgreSQL

## 🔧 下一步

1. 配置真实的 OpenAI API Key
2. 为商品生成 Embedding 向量
3. 配合前端项目进行联调测试
4. 完善错误处理和日志记录

---

**更多详情请查看：**

- [README.md](./README.md) - 项目概述
- [QUICKSTART.md](./QUICKSTART.md) - 快速开始指南
- [API 文档](http://localhost:8000/docs) - Swagger UI (启动后访问)
