# AI 电商平台 - 后端 API

基于 FastAPI + SQLAlchemy 2.0 + OpenAI 的轻量级电商后端系统。

## 技术栈

- **Web 框架**: FastAPI (异步高性能)
- **ORM**: SQLAlchemy 2.0 (异步模式)
- **数据库**: SQLite (WAL 模式)
- **数据验证**: Pydantic v2
- **安全**: Bcrypt + PyJWT
- **AI**: OpenAI API + Numpy (本地向量计算)

## 快速启动

1. 安装依赖:

```bash
pip install -r requirements.txt
```

2. 配置环境变量:

```bash
cp .env.example .env
# 编辑 .env 文件,填入你的 OpenAI API Key
```

3. 启动服务:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. 访问 API 文档:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 项目结构

```
app/
├── core/           # 核心配置
│   ├── config.py   # 环境变量加载
│   └── security.py # 密码哈希 & JWT
├── db/             # 数据库
│   ├── database.py # 连接池配置
│   └── models.py   # SQLAlchemy 模型
├── schemas/        # Pydantic 模式
├── api/            # API 路由
│   ├── deps.py     # 依赖注入
│   └── routers/    # 路由模块
├── services/       # 业务逻辑层
└── main.py         # 应用入口
```

## 核心特性

✅ JWT 双 Token 无状态认证 (Access + Refresh)
✅ 原子库存扣减防超卖 (SQLite 事务)
✅ 订单地址/价格快照设计
✅ OpenAI 智能推荐 + SSE 流式输出
✅ 本地 Numpy 向量相似度计算
