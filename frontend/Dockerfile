FROM nginx:latest

# 生产镜像直接使用本机已经构建好的前端产物，避免再次拉取 Node 依赖
COPY dist /usr/share/nginx/html

# 使用自定义 Nginx 配置：
# - 前端静态资源由 Nginx 提供
# - /api 与 /uploads 反向代理到 backend:8000
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 对外暴露 5181 端口，保持与当前本地访问习惯一致
EXPOSE 5181
