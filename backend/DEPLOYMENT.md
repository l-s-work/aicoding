# 生产环境部署指南

## 📦 部署方式选择

### 方案 A：传统服务器部署（推荐小型项目）

#### 1. 服务器目录结构

```
/var/www/ecommerce/
├── backend/              # 应用代码
│   ├── app/
│   ├── scripts/
│   └── .env             # 生产环境配置
└── data/                # 数据目录（独立于代码）
    ├── ecommerce.db     # SQLite 数据库
    ├── ecommerce.db-shm
    ├── ecommerce.db-wal
    └── backups/         # 数据库备份
```

#### 2. 环境配置 (.env)

```env
# 使用绝对路径，数据与代码分离
DATABASE_URL=sqlite+aiosqlite:////var/www/ecommerce/data/ecommerce.db
DEBUG=false
JWT_SECRET_KEY=<strong-random-key>
```

#### 3. 创建数据目录

```bash
# 创建数据目录
sudo mkdir -p /var/www/ecommerce/data/backups

# 设置权限
sudo chown -R www-data:www-data /var/www/ecommerce/data
sudo chmod 755 /var/www/ecommerce/data
```

#### 4. systemd 服务配置

创建 `/etc/systemd/system/ecommerce-backend.service`：

```ini
[Unit]
Description=AI E-commerce Backend API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/ecommerce/backend
Environment="PATH=/var/www/ecommerce/venv/bin"
ExecStart=/var/www/ecommerce/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable ecommerce-backend
sudo systemctl start ecommerce-backend
```

---

### 方案 B：Docker 部署（推荐中大型项目）

#### 1. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY scripts/ ./scripts/

# 创建数据目录（将被数据卷覆盖）
RUN mkdir -p /app/data

# 环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. docker-compose.yml

```yaml
version: "3.8"

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      # 数据卷挂载 - 数据库文件持久化
      - ./data:/app/data
      # 配置文件挂载
      - ./.env:/app/.env
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////app/data/ecommerce.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### 3. 启动容器

```bash
# 创建数据目录
mkdir -p data

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

**数据库位置：**

- 容器内：`/app/data/ecommerce.db`
- 宿主机：`./data/ecommerce.db`（持久化存储）

---

### 方案 C：云服务部署

#### 阿里云 ECS / 腾讯云 CVM

```bash
# 推荐目录结构
/www/wwwroot/ecommerce/
├── backend/
├── data/              # 挂载独立数据盘
│   └── ecommerce.db

# 配置 .env
DATABASE_URL=sqlite+aiosqlite:////www/wwwroot/ecommerce/data/ecommerce.db
```

#### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## 🔒 数据安全建议

### 1. 定期备份脚本

创建 `scripts/backup_db.sh`：

```bash
#!/bin/bash
BACKUP_DIR="/var/www/ecommerce/data/backups"
DB_FILE="/var/www/ecommerce/data/ecommerce.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建备份
cp "$DB_FILE" "$BACKUP_DIR/ecommerce_$TIMESTAMP.db"

# 保留最近 7 天的备份
find "$BACKUP_DIR" -name "ecommerce_*.db" -mtime +7 -delete

echo "Backup completed: ecommerce_$TIMESTAMP.db"
```

设置 cron 定时任务：

```bash
# 每天凌晨 2 点备份
0 2 * * * /var/www/ecommerce/backend/scripts/backup_db.sh
```

### 2. 文件权限设置

```bash
# 数据库文件仅应用用户可读写
chmod 600 /var/www/ecommerce/data/ecommerce.db

# 数据目录设置
chmod 700 /var/www/ecommerce/data
```

---

## ⚡ 性能优化建议

### 对于 SQLite

#### 优点

- ✅ 部署简单，无需额外数据库服务
- ✅ 适合小型项目（< 1万用户，< 100并发）
- ✅ 备份简单（直接复制文件）

#### 限制

- ❌ 写并发受限（单线程写）
- ❌ 不支持分布式部署
- ❌ 文件大小限制（建议 < 1GB）

### 迁移到 PostgreSQL（推荐生产环境）

当你的用户量增长到一定规模，建议迁移到 PostgreSQL：

#### 1. 安装 PostgreSQL 驱动

```bash
pip install asyncpg
```

#### 2. 修改 .env

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ecommerce
```

#### 3. 数据迁移

使用 Alembic 进行数据库迁移：

```bash
# 初始化 Alembic
alembic init alembic

# 生成迁移文件
alembic revision --autogenerate -m "Initial migration"

# 执行迁移
alembic upgrade head
```

---

## 📊 监控和运维

### 1. 日志管理

```python
# 在 main.py 中添加日志配置
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/ecommerce/backend.log'),
        logging.StreamHandler()
    ]
)
```

### 2. 健康检查

```bash
# 定时检查 API 健康状态
*/5 * * * * curl -f http://localhost:8000/health || systemctl restart ecommerce-backend
```

---

## 🚨 常见问题

### Q: 容器重启后数据丢失怎么办？

A: 使用 Docker 数据卷挂载：

```yaml
volumes:
  - ./data:/app/data
```

### Q: 数据库文件越来越大怎么办？

A: 定期执行 VACUUM 清理：

```bash
sqlite3 /var/www/ecommerce/data/ecommerce.db "VACUUM;"
```

### Q: 如何实现零停机部署？

A: 使用 Nginx + 多实例 + 滚动更新：

```bash
# 启动新实例（端口 8001）
# 更新 Nginx 配置指向新实例
# 优雅关闭旧实例
```

---

## 📝 部署检查清单

部署前确保：

- [ ] 修改 JWT_SECRET_KEY 为强随机密钥
- [ ] 修改默认管理员密码
- [ ] DEBUG 设置为 false
- [ ] 配置 CORS 仅允许生产域名
- [ ] 使用绝对路径存储数据库
- [ ] 设置数据目录权限
- [ ] 配置定期备份任务
- [ ] 配置日志收集
- [ ] 配置健康检查
- [ ] 配置 HTTPS（使用 Let's Encrypt）
- [ ] 配置防火墙规则
- [ ] 测试数据恢复流程

---

## 📚 相关文档

- [FastAPI 部署文档](https://fastapi.tiangolo.com/deployment/)
- [SQLite 生产环境最佳实践](https://www.sqlite.org/howtocorrupt.html)
- [Docker 部署指南](https://docs.docker.com/compose/)
