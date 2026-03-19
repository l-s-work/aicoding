# AI 编码智能体指令 (Project: AI E-commerce)

## 1. 项目概览与核心原则

这是我们 AI 驱动的电商系统的专属指南。在接下来的所有代码生成中，你必须**严格遵守**以下架构规范，不可偏离。

- **核心原则**：轻量化。拒绝过度工程化。
- **语言**：TypeScript（前端）和 Python（后端）。所有代码必须包含必要的类型推导和错误处理。

## 2. 前端架构规范 (Frontend)

前端项目基于单一 `Vite` 项目进行路由层面的端隔离，且采用最新版特性。

- **技术栈**：React 19 + TypeScript + Vite + pnpm。
- **状态管理**：Zustand（针对购物车等跨页面共享数据开启 `persist` 缓存）。
- **路由控制**：React Router v7（向下兼容 v6 API，使用 `createBrowserRouter` + `<PrivateRoute>` 严格区分 `src/pages/client` 和 `src/pages/admin`）。
- **组件与样式**：
  - **组件库**：Ant Design v6。
  - **AI 组件**：Ant Design X (`@ant-design/x`)。
  - **样式方案**：`styled-components` (CSS-in-JS)。**绝对禁止使用 Tailwind CSS 或冗杂的 className 堆砌**。

## 3. 后端架构规范 (Backend)

后端为轻量极速架构，专为小型及单机部署优化。

- **技术栈**：Python + FastAPI + SQLAlchemy 2.0 (Async) + Pydantic v2。
- **数据库**：单一 **SQLite**。
  - 必须开启 `WAL` 模式（`PRAGMA journal_mode=WAL`）。
  - 数据库连接禁止同线程校验（`check_same_thread=False`）。
- **AI 智能整合**：
  - LLM 对接：OpenAI 官方 SDK。
  - 向前端暴露基于 `Server-Sent Events (SSE)` 的多模态打字机接口。
  - 向量搜索：拒绝重量级向量数据库，**使用本地纯 `Numpy` 库计算嵌入向量(Embeddings)余弦相似度**。

## 4. 核心业务领域模型规范 (Domain Rules)

当编写以下特定业务逻辑时，必须准守这组“数据快照”防腐录入原则：

1. **商品库存并发控制**：不使用 Redis 分布式锁，直接依靠 SQLite 事务和行级（单点）Atomic 扣减指令解决并发超卖。
2. **收货地址逻辑**：地址表（多地址）与最终订单无关。用户下单时，必须将选定的地址**拍屏式（硬拷贝）**作为一个大 JSON 字符串写入订单的 `receiver_info` 字段。
3. **购物车与订单结账**：
   - 订单表中禁止以 Foreign Key 关联商品表中的价格。
   - 创建订单时，不仅要记下 `product_id`，还必须把彼时的购买价格（`buy_price`）作为独立字段永久固化到大订单的关联 Item 表中。
4. **安全与登录踢出**：
   - 使用 JWT 无状态鉴权但配有 `refresh_tokens` 拦截表。
   - 当用户异地登录或主动退出时，在拦截表中标记 Token 为无效，从而实现前端 HTTP Response `401/403` 的联锁清退动作。

## 5. 代码输出格式要求

- 代码应有充足的中文注释解释业务逻辑（尤其是 AI 路由与计算分离）。
- 在修改既有文件时，必须先结合上下文阅读，不得擅自抹除他人的逻辑。
- 每完成一个组件或 API 路由，必须同时在响应结尾处提供一个可用于联调的简单使用示例（例如使用 Axios 怎么调，或者怎样渲染该组件）。
