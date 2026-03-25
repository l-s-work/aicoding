# 本地 Docker 部署方案（当前仓库实配版）

## 1. 文档目标

本方案基于当前仓库**现有文件与配置**整理，目标是让你在本机（Windows + Docker Desktop）快速完成：

- 前后端一体化容器部署（推荐）
- 仅后端容器部署（可选）
- SQLite 数据与上传文件持久化
- 启动后健康检查与联调验证

> 适用项目根目录：`D:\AICoding作业`

---

## 2. 当前仓库 Docker 资产梳理

### 2.1 编排文件

- 根目录：`docker-compose.yml`（前后端一体化）
- 后端目录：`backend/docker-compose.yml`（仅后端）

### 2.2 镜像构建特性（关键）

当前仓库 Dockerfile 不是“从零完整构建”，而是“增量复用”：

1. `backend/Dockerfile` 以 `aicoding-backend:latest` 作为基础镜像，仅覆盖 `app/` 与 `scripts/`。
2. `frontend/Dockerfile` 直接 `COPY dist` 到 Nginx，因此要求本地先有 `frontend/dist`。

这意味着你本地需要满足两个前置条件：

- 已存在 `aicoding-backend:latest` 镜像（或你先构建一个同名镜像）。
- 已执行过前端打包，产物存在 `frontend/dist`。

---

## 3. 方案 A：全栈本地部署（推荐）

使用根目录 `docker-compose.yml`，一次拉起：

- `ecommerce-backend`（8000）
- `ecommerce-frontend`（5181，Nginx 反代 `/api` 与 `/uploads` 到后端）

### 3.1 前置检查

在项目根目录执行：

```powershell
cd D:\AICoding作业
docker --version
docker compose version
```

准备后端环境变量（若不存在）：

```powershell
cd D:\AICoding作业\backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

建议至少确认 `.env` 中以下变量已填写：

```env
JWT_SECRET_KEY=请改成强随机字符串
OPENAI_API_KEY=你的密钥
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_BASE_URL=https://api.openai.com/v1
CORS_ORIGINS=http://localhost:5181,http://127.0.0.1:5181
```

检查前端打包产物：

```powershell
cd D:\AICoding作业
if (!(Test-Path frontend/dist)) {
  cd frontend
  pnpm install
  pnpm build
  cd ..
}
```

检查后端基础镜像是否存在：

```powershell
docker image inspect aicoding-backend:latest > $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "缺少 aicoding-backend:latest，请先构建或导入该镜像。"
}
```

### 3.2 启动

```powershell
cd D:\AICoding作业
docker compose up -d --build
```

查看状态与日志：

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

### 3.3 访问入口

- 前端：`http://localhost:5181`
- 后端健康检查：`http://localhost:8000/health`
- 后端 Swagger：`http://localhost:8000/docs`

---

## 4. 方案 B：仅后端容器部署（可选）

使用 `backend/docker-compose.yml`，适合你只调 API 或单独联调后端。

```powershell
cd D:\AICoding作业\backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

访问：

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

---

## 5. 数据持久化与目录映射

根目录编排下的关键挂载：

- `./data -> /app/data`：SQLite 数据库文件持久化
- `./backend/uploads -> /app/uploads`：商品图片/上传资源持久化

数据库实际路径（容器内）：

- `/app/data/ecommerce.db`

由于后端连接参数固定为 `check_same_thread=False`，并在连接事件中设置 `PRAGMA journal_mode=WAL`，符合当前项目“SQLite 轻量并发”要求。

---

## 6. 常见问题与排障

### 6.1 `docker compose up` 报无法连接 daemon

现象：提示无法连接 `dockerDesktopLinuxEngine`。  
处理：先启动 Docker Desktop，等待 Engine 就绪后重试。

### 6.2 `FROM aicoding-backend:latest` 拉取失败

原因：该镜像是本地基础镜像名，不一定在公共仓库可拉取。  
处理：让项目维护者提供镜像导入包，或在本机构建同名基础镜像后再 `compose up`。

### 6.3 前端容器构建失败（`COPY dist` 失败）

原因：`frontend/dist` 不存在。  
处理：先在 `frontend` 执行 `pnpm build` 再重新构建。

### 6.4 容器启动后前端白屏或 API 404

排查顺序：

1. `docker compose ps` 确认 `backend` 和 `frontend` 都是 `Up`。
2. 访问 `http://localhost:8000/health` 确认后端正常。
3. 查看前端 Nginx 日志与后端日志，确认 `/api/*` 是否到达后端。

### 6.5 需要彻底重建环境

```powershell
cd D:\AICoding作业
docker compose down
docker compose up -d --build --force-recreate
```

如需清理无用镜像/构建缓存（谨慎）：

```powershell
docker image prune -f
docker builder prune -f
```

---

## 7. 最短可执行命令清单（全栈）

```powershell
cd D:\AICoding作业\backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }

cd D:\AICoding作业\frontend
pnpm install
pnpm build

cd D:\AICoding作业
docker compose up -d --build
docker compose ps
```

---

## 8. 联调验证示例

### 8.1 健康检查

```powershell
curl http://localhost:8000/health
```

预期返回示例：

```json
{
  "status": "healthy",
  "app": "AI电商平台",
  "version": "1.0.0"
}
```

### 8.2 前端通过网关访问 API（Axios）

```ts
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

async function pingProducts() {
  const res = await api.get('/products', { params: { page: 1, page_size: 10 } });
  console.log(res.data);
}
```

