# AI 电商平台后端说明

基于 FastAPI + SQLAlchemy 2.0 Async + SQLite + OpenAI SDK 的轻量级 AI 电商后端，服务于当前仓库中的前后端一体化项目。系统围绕“商城基础流程 + AI 助手 + 轻量部署”设计，适合课程作业、小型项目和单机部署场景。

## 项目定位

当前项目已经具备一套完整的电商核心链路：

- 买家端：注册、登录、找回密码、商品浏览、购物车、地址管理、下单、支付、取消订单、确认收货
- 管理端：商品管理、分类管理、订单管理、用户管理、封禁与解封、账号恢复申请处理、商品统计看板
- AI 能力：商品推荐、订单问答、地址识别、账号信息问答、多轮历史记录、SSE 流式输出
- 数据设计：订单地址快照、下单价格快照、SQLite 原子扣库存、防止历史数据被后续商品信息污染

## 技术栈

- Web 框架：FastAPI
- ORM：SQLAlchemy 2.0 Async
- 数据验证：Pydantic v2
- 数据库：SQLite
- 并发策略：`WAL` 模式 + `check_same_thread=False`
- 鉴权：JWT Access Token + Refresh Token + 拦截表
- AI：OpenAI SDK
- 向量检索：本地 Numpy 余弦相似度计算
- 流式响应：Server-Sent Events（SSE）

## 当前已实现的核心功能

### 1. 用户认证与账号安全

- 用户注册、登录、刷新令牌、退出当前设备、退出全部设备
- 登录失败次数限制，连续失败会临时锁定账号
- 支持忘记密码直接重置
- 支持管理员封禁/解封用户
- 支持封禁用户提交账号恢复申请，管理员可审批
- 前端收到 `401/403` 后可联动清退，保证登录状态一致

### 2. 商品与分类管理

- 商品三级分类树
- 商品列表分页、关键词搜索、按分类级联筛选
- 商品 CRUD
- 商品图片上传与静态资源访问
- 商品 Embedding 状态跟踪
- 商品名称或描述变更后自动触发重新向量化

### 3. 订单与库存

- 创建订单时校验库存并原子扣减
- 使用地址快照写入 `orders.receiver_info`
- 使用价格快照写入 `order_items.buy_price`
- 支持待支付、已支付、已发货、已完成、已取消状态流转
- 取消订单时自动回滚库存
- 管理员可查看全量订单并更新状态

### 4. 地址管理

- 每个用户最多 5 个地址
- 支持默认地址
- 删除默认地址后自动补一个新的默认地址
- 下单时只读取地址表，真正写入订单的是地址快照

### 5. AI 智能助手

- 提供普通 JSON 对话接口与 SSE 流式接口
- 支持商品推荐、订单解释、地址识别、账号信息解答
- 支持结构化卡片返回，便于前端直接渲染
- 支持保存与清空历史对话记录
- 商品 Embedding 存本地数据库，通过 Numpy 计算相似度，不依赖重量级向量库

### 6. 管理端能力

- 商品统计看板
- 在售/下架/低库存/缺货统计
- 热门商品排行
- 分类商品数 Top 列表
- 用户状态管理与密码重置
- 账号恢复申请审批

## 关键业务设计

### 订单快照设计

- 地址不会和历史订单强绑定关联
- 用户下单时，所选地址会被完整复制到 `receiver_info`
- 订单商品会记录 `product_id + product_name + buy_price + quantity`
- 商品以后涨价、改名、删地址，都不会影响历史订单展示

### SQLite 防超卖策略

- 不引入 Redis 分布式锁
- 下单时在事务中进行条件更新扣库存
- 扣减失败直接回滚，避免超卖

### 鉴权与踢出机制

- Access Token 负责接口访问
- Refresh Token 保存到 HttpOnly Cookie
- 主动退出时写入 Access Token 拦截表并删除对应 Refresh Token
- 异地登录、改密、封禁时通过 `token_version` 让旧会话失效

## 项目结构

```text
backend/
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── routers/
│   │       ├── _auth.py
│   │       ├── _product.py
│   │       ├── _order.py
│   │       ├── _address.py
│   │       ├── _ai.py
│   │       └── _admin.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   ├── schemas/
│   ├── services/
│   │   ├── ai_service.py
│   │   └── order_service.py
│   └── main.py
├── scripts/
│   ├── dev_server.py
│   └── init_db.py
├── uploads/
├── .env.example
├── requirements.txt
└── README.md
```

## 快速启动

### 1. 安装依赖

建议在仓库根目录的 Python 环境中执行：

```powershell
cd D:\AICoding作业
python -m pip install -r backend\requirements.txt
```

### 2. 配置环境变量

先复制模板：

```powershell
cd D:\AICoding作业\backend
Copy-Item .env.example .env
```

然后至少补齐这些配置：

```env
JWT_SECRET_KEY=your-jwt-secret
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_BASE_URL=https://api.openai.com/v1
```

如果你需要让浏览器直接跨域访问后端，可把前端开发端口加入：

```env
CORS_ORIGINS=http://localhost:5180,http://127.0.0.1:5180
```

### 3. 初始化数据库与示例数据

```powershell
cd D:\AICoding作业\backend
python scripts\init_db.py
```

初始化脚本会创建：

- 数据表结构
- 默认管理员账号：`admin / admin123`
- 示例三级商品分类
- 示例商品数据

### 4. 启动后端服务

```powershell
cd D:\AICoding作业\backend
python scripts\dev_server.py
```

或直接使用 `uvicorn`：

```powershell
cd D:\AICoding作业\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 启动后可访问

- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`
- 健康检查：`http://127.0.0.1:8000/health`

## 与前端联调

当前仓库前端使用 React 19 + Vite，开发默认端口为 `5180`，并通过 Vite 代理把 `/api` 转发到 `http://127.0.0.1:8000`。

前端启动命令：

```powershell
cd D:\AICoding作业\frontend
pnpm install
pnpm dev
```

联调时建议按下面顺序检查：

1. 打开 `http://127.0.0.1:8000/health`，确认后端正常
2. 打开 `http://localhost:5180`，确认前端正常
3. 在浏览器 Network 中确认前端请求路径是 `/api/...`
4. 若请求失败，再检查后端终端日志与 `/docs` 中的接口定义

## 主要 API 模块

### 认证模块 `/auth`

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/logout-all`
- `GET /auth/me`
- `PUT /auth/me`
- `POST /auth/change-password`
- `POST /auth/forgot-password`
- `POST /auth/recovery-request`

### 商品模块 `/products`

- `GET /products`
- `GET /products/{product_id}`
- `POST /products`
- `PUT /products/{product_id}`
- `DELETE /products/{product_id}`
- `GET /products/categories`
- `POST /products/categories`
- `POST /products/upload-image`
- `POST /products/{product_id}/embedding/sync`

### 订单模块 `/orders`

- `POST /orders`
- `GET /orders`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/pay`
- `POST /orders/{order_id}/cancel`
- `POST /orders/{order_id}/confirm-receipt`
- `GET /orders/admin/all`
- `GET /orders/admin/{order_id}`
- `PUT /orders/admin/{order_id}/status`

### 地址模块 `/addresses`

- `GET /addresses`
- `GET /addresses/{address_id}`
- `POST /addresses`
- `PUT /addresses/{address_id}`
- `DELETE /addresses/{address_id}`
- `POST /addresses/{address_id}/set-default`

### AI 模块 `/ai`

- `POST /ai/chat`
- `POST /ai/chat/stream`
- `GET /ai/history`
- `DELETE /ai/history`
- `POST /ai/products/{product_id}/sync-embedding`

### 管理模块 `/admin`

- `GET /admin/dashboard/stats`
- `GET /admin/users`
- `PATCH /admin/users/{user_id}/status`
- `POST /admin/users/{user_id}/reset-password`
- `GET /admin/recovery-requests`
- `PUT /admin/recovery-requests/{request_id}/process`

## 联调示例

### Axios 登录示例

```ts
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

async function login() {
  const res = await api.post('/auth/login', {
    username: 'admin',
    password: 'admin123',
  });

  console.log(res.data.access_token);
  console.log(res.data.user);
}
```

### 创建订单示例

```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "address_id": 1,
    "items": [
      { "product_id": 1, "quantity": 1 },
      { "product_id": 2, "quantity": 2 }
    ]
  }'
```

### AI 流式对话示例

```ts
const response = await fetch('/api/ai/chat/stream', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  },
  body: JSON.stringify({
    content: '帮我推荐几款性价比高的商品',
    context: {
      page_type: 'home',
      page_path: '/',
    },
  }),
});
```

## 常见问题

### 1. `/health` 打不开

先确认服务是否真的启动在 `8000` 端口，并检查终端里是否有导入失败、环境变量缺失或端口占用错误。

### 2. OpenAI 调用失败

优先检查：

- `.env` 中 `OPENAI_API_KEY` 是否正确
- 网络是否能访问 OpenAI 接口
- 账户额度是否可用

### 3. 前端请求不到后端

优先检查：

- 前端是否运行在 `5180`
- 请求路径是否以 `/api` 开头
- `frontend/vite.config.ts` 的代理目标是否仍为 `http://127.0.0.1:8000`

### 4. 登录后马上被踢出

通常要检查：

- Access Token 是否真的写入前端状态
- 浏览器是否允许携带 Cookie
- Refresh Token 是否被清理或失效
- 当前账号是否已被管理员封禁

## 说明补充

- 数据库采用 SQLite，适合轻量开发与课程项目
- 生产环境必须替换默认管理员密码和 `JWT_SECRET_KEY`
- 商品 Embedding 与 AI 问答依赖外部模型服务，未配置密钥时相关能力无法正常工作

更多细节可以继续结合以下文件阅读：

- `backend/QUICKSTART.md`
- `backend/PROJECT_SUMMARY.md`
- `frontend/src/router/index.tsx`
- `frontend/src/components/ai/ClientAiAssistant.tsx`
