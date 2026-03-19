# 后端快速开始指南

## 第一步：环境准备

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```env
# 必须配置的项目
JWT_SECRET_KEY=your-super-secret-jwt-key-please-change-this
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 可选配置
CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
```

**重要提示**：

- `JWT_SECRET_KEY` 请使用强随机字符串（生产环境）
- `OPENAI_API_KEY` 从 OpenAI 官网获取

## 第二步：初始化数据库

```bash
python scripts/init_db.py
```

这将创建：

- ✅ 数据库表结构
- ✅ 管理员账户（admin / admin123）
- ✅ 示例商品分类
- ✅ 示例商品数据

## 第三步：启动服务

### 方式一：使用脚本（推荐）

```bash
python scripts/dev_server.py
```

### 方式二：直接使用 uvicorn

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 第四步：访问 API 文档

启动后访问：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health

## API 快速测试

### 1. 注册用户

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "test1234"
  }'
```

### 2. 登录获取 Token

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "test1234"
  }'
```

### 3. 获取商品列表

```bash
curl http://localhost:8000/products?page=1&page_size=10
```

### 4. AI 对话（需要先登录）

```bash
curl -X POST http://localhost:8000/ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "content": "推荐一款性价比高的手机"
  }'
```

## 常见问题

### Q: ModuleNotFoundError: No module named 'xxx'

A: 请确保已安装所有依赖：`pip install -r requirements.txt`

### Q: OpenAI API 调用失败

A: 请检查：

1. `.env` 文件中的 `OPENAI_API_KEY` 是否正确
2. 网络是否能访问 OpenAI API
3. API Key 是否有余额

### Q: CORS 错误

A: 在 `.env` 中配置前端地址：

```env
CORS_ORIGINS=http://localhost:5174
```

### Q: 数据库锁定错误

A: SQLite 已配置 WAL 模式，如仍有问题，请确保：

1. 没有多个进程同时访问数据库
2. 数据库文件有写入权限

## 目录结构说明

```
backend/
├── app/                    # 应用主目录
│   ├── core/              # 核心配置
│   │   ├── config.py      # 环境变量配置
│   │   └── security.py    # 安全相关（JWT、密码哈希）
│   ├── db/                # 数据库
│   │   ├── database.py    # 连接配置
│   │   └── models.py      # ORM 模型
│   ├── schemas/           # Pydantic 数据模型
│   ├── api/               # API 路由
│   │   ├── deps.py        # 依赖注入
│   │   └── routers/       # 路由模块
│   │       ├── _auth.py   # 认证路由
│   │       ├── _product.py# 商品路由
│   │       ├── _order.py  # 订单路由
│   │       ├── _address.py# 地址路由
│   │       └── _ai.py     # AI 对话路由
│   ├── services/          # 业务逻辑层
│   │   ├── order_service.py    # 订单服务
│   │   └── ai_service.py       # AI 服务
│   └── main.py            # FastAPI 应用入口
├── scripts/               # 工具脚本
│   ├── init_db.py         # 初始化数据库
│   └── dev_server.py      # 开发服务器
├── requirements.txt       # Python 依赖
├── .env.example          # 环境变量模板
└── README.md             # 项目说明

```

## 下一步

1. 阅读 API 文档了解所有接口
2. 配合前端项目进行联调
3. 使用 AI 对话功能前，需先为商品生成 Embedding

## 技术支持

遇到问题请检查：

1. 日志输出
2. API 文档中的错误响应说明
3. 数据库数据是否正确
