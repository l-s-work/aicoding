# AI 电商作业 PRD

## 1. 项目背景

本项目旨在完成一个“小型 AI 驱动电商平台”课程作业，要求在基础电商闭环之外，加入真实可用的 AI 助手能力，并且坚持轻量化架构，不引入复杂中间件和重型基础设施。

当前项目已经实现前后端联动闭环，覆盖：

- 用户注册、登录、找回密码、账号安全
- 商品浏览、购物车、结算、订单、地址管理
- 管理员商品管理、订单管理、用户管理、看板与待办
- AI 助手对商品、订单、地址、账号信息的理解和回答

## 2. 项目目标

### 2.1 业务目标

- 完成一个可演示的电商主流程
- 体现 AI 与业务页面、业务数据的真实融合
- 同时具备 C 端与 B 端管理能力

### 2.2 技术目标

- 前端使用 React 19 + TypeScript + Vite
- 后端使用 FastAPI + SQLAlchemy 2.0 Async + SQLite
- 鉴权采用 JWT + Refresh Token
- AI 对话支持 SSE 流式输出
- 商品语义检索使用本地 Numpy 相似度计算

## 3. 用户角色

### 3.1 C 端用户

能力包括：

- 注册和登录
- 浏览商品
- 加入购物车
- 立即购买
- 管理地址
- 查看订单
- 修改个人资料
- 与 AI 助手对话

### 3.2 管理员

能力包括：

- 登录后台
- 查看商品统计
- 管理商品与分类
- 管理订单
- 管理用户
- 处理账号恢复申请
- 查看待发货订单

## 4. 产品范围

### 4.1 C 端需求

### 4.1.1 账号体系

必须支持：

- 注册
- 登录
- 忘记密码
- 修改资料
- 修改密码
- 退出当前设备
- 退出所有设备

当前实现说明：

- 忘记密码采用“用户名 + 邮箱 + 新密码”的轻量重置方式
- 封禁用户可在登录页提交恢复申请

### 4.1.2 商品浏览

必须支持：

- 商品列表页
- 商品详情页
- 商品关键词搜索
- 商品分类筛选
- 商品状态展示

当前实现页面：

- `/`
- `/product/:id`

### 4.1.3 购物车与结算

必须支持：

- 加入购物车
- 删除购物车商品
- 勾选部分商品去结算
- 立即购买
- 选择收货地址
- 调整本次购买数量
- 提交订单

当前实现说明：

- 购物车保存在前端本地，不做服务端购物车表
- 提交订单后当前版本直接记为已支付

### 4.1.4 地址管理

必须支持：

- 地址新增
- 地址编辑
- 地址删除
- 默认地址设置

当前实现页面：

- `/addresses`

### 4.1.5 订单管理

必须支持：

- 订单列表
- 订单详情
- 按状态筛选
- 按商品名称搜索
- 确认收货

当前实现页面：

- `/orders`
- `/orders/:id`

### 4.1.6 AI 智能助手

必须支持：

- 全局浮动入口
- SSE 流式输出
- Markdown 回复渲染
- 商品推荐
- 订单答疑
- 地址识别
- 账号资料问答

当前实现说明：

- AI 助手已挂在 C 端全局布局中
- AI 不只是文本闲聊，而是可返回结构化卡片

### 4.2 B 端需求

### 4.2.1 Dashboard

必须支持：

- 商品总数
- 在售数
- 下架数
- 低库存数
- 缺货数
- 分类数
- 商品状态分布
- 分类商品数 Top
- 热门商品 Top

当前实现页面：

- `/admin/dashboard`

### 4.2.2 我的待办

必须支持：

- 查看待处理恢复申请
- 查看待发货订单
- 快捷处理恢复申请
- 快捷发货

当前实现页面：

- `/admin/todos`

### 4.2.3 商品管理

必须支持：

- 商品分页管理
- 商品新建
- 商品编辑
- 分类新建
- 单图上传
- 商品状态筛选
- 分类筛选
- 向量状态查看
- 重新向量化

当前实现页面：

- `/admin/products`
- `/admin/products/new`
- `/admin/products/:id/edit`

### 4.2.4 订单管理

必须支持：

- 查看全量订单
- 按状态筛选
- 按收货人/用户名搜索
- 按商品名称搜索
- 查看详情
- 更新订单状态

当前实现页面：

- `/admin/orders`

### 4.2.5 用户管理

必须支持：

- 用户分页查询
- 用户状态筛选
- 用户名/邮箱搜索
- 封禁/解封用户
- 重置用户密码

当前实现页面：

- `/admin/users`

### 4.3 后端支撑需求

必须支持：

- 统一鉴权
- 角色区分
- Session 失效控制
- SQLite WAL 模式
- 原子扣减库存
- 地址快照
- 价格快照
- AI 流式输出

## 5. 核心业务规则

### 5.1 鉴权规则

- Access Token 用于访问接口
- Refresh Token 放在 HttpOnly Cookie
- 用户主动退出当前设备时，当前 Access Token 要立即失效
- 用户退出全部设备、改密或被封禁时，旧会话全部失效

### 5.2 商品分类规则

- 分类最大三级
- 商品只能挂在三级分类下
- `category_code` 由后端自动生成

### 5.3 订单规则

- 订单地址使用快照，不关联地址表
- 订单价格使用快照，不依赖商品现价
- 扣库存必须在事务中原子完成
- 取消订单时要回滚库存

### 5.4 地址规则

- 每个用户最多 5 个地址
- 同一用户只能有一个默认地址
- 第一个地址自动为默认

### 5.5 AI 规则

- AI 只能基于后端准备的业务快照回答
- 不直接访问数据库
- 不编造订单、地址、账号等私有数据

## 6. 当前接口范围

### 6.1 认证接口

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

### 6.2 商品接口

- `GET /products`
- `GET /products/{product_id}`
- `POST /products`
- `PUT /products/{product_id}`
- `DELETE /products/{product_id}`
- `GET /products/categories`
- `POST /products/categories`
- `POST /products/upload-image`
- `POST /products/{product_id}/embedding/sync`

### 6.3 订单接口

- `POST /orders`
- `GET /orders`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/pay`
- `POST /orders/{order_id}/cancel`
- `POST /orders/{order_id}/confirm-receipt`
- `GET /orders/admin/all`
- `GET /orders/admin/{order_id}`
- `PUT /orders/admin/{order_id}/status`

### 6.4 地址接口

- `GET /addresses`
- `GET /addresses/{address_id}`
- `POST /addresses`
- `PUT /addresses/{address_id}`
- `DELETE /addresses/{address_id}`
- `POST /addresses/{address_id}/set-default`

### 6.5 AI 接口

- `POST /ai/chat`
- `POST /ai/chat/stream`
- `GET /ai/history`
- `DELETE /ai/history`
- `POST /ai/products/{product_id}/sync-embedding`

### 6.6 管理接口

- `GET /admin/dashboard/stats`
- `GET /admin/users`
- `PATCH /admin/users/{user_id}/status`
- `POST /admin/users/{user_id}/reset-password`
- `GET /admin/recovery-requests`
- `PUT /admin/recovery-requests/{request_id}/process`

## 7. 验收标准

### 7.1 基础链路

- 用户可完成注册、登录、忘记密码
- 普通用户登录后进入 `/`
- 管理员登录后进入 `/admin/dashboard`
- 未登录访问受保护页面时会被拦截

### 7.2 电商链路

- 用户可浏览商品、加入购物车、立即购买
- 用户可管理地址并在结算页选择地址
- 用户可提交订单并查看订单详情
- 管理员可查看订单并更新状态

### 7.3 安全链路

- 连续输错密码 5 次会被临时锁定
- 退出当前设备后当前 Token 立即失效
- 退出全部设备后旧会话不可再用
- 管理员封禁用户后，该用户访问受保护接口应返回 403

### 7.4 AI 链路

- AI 助手可在 C 端页面中正常打开
- 支持流式输出
- 可回答商品、订单、地址、账号相关问题
- 可返回结构化卡片

## 8. 非功能要求

### 8.1 架构要求

- 保持轻量化
- 不引入 Redis
- 不引入重量级向量数据库
- 单机可完整运行

### 8.2 代码要求

- 前端使用 TypeScript
- 后端使用 Python + 类型校验
- 关键业务逻辑要有清晰注释
- 文档与代码实现保持一致

### 8.3 体验要求

- 登录态尽量无感续期
- AI 回复支持流式展示
- 页面具备基础错误提示和空状态

## 9. 当前版本总结

当前作业版本已经不只是“原型设计”，而是一个可以实际演示的完整项目：

- 电商主流程可跑通
- 后台管理可使用
- AI 助手与真实业务数据已打通
- 登录安全、快照设计、库存事务等核心设计已落地

后续若继续扩展，可以围绕：

- 真实支付
- 售后退款
- 多图商品
- 更强的 AI 工具调用
- 自动化测试

继续演进。
