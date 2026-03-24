FROM aicoding-backend:latest

# 复用本机已经构建好的后端运行环境，只覆盖最新的业务代码
WORKDIR /app

# 当前镜像内已包含 Python、依赖、appuser、uvicorn 与健康检查配置
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser scripts/ ./scripts/
