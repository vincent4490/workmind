#!/bin/bash
# Workmind 一键部署脚本（在服务器 /data/workmind 下执行）
# 会创建/使用 backend/venv、安装依赖、migrate、collectstatic、构建前端

set -e
cd /data/workmind

echo "=== 1. 后端虚拟环境与依赖 ==="
if [ ! -d backend/venv ]; then
    python3.9 -m venv backend/venv || python3 -m venv backend/venv
fi
source backend/venv/bin/activate
pip install -r backend/requirements.txt -q

echo "=== 2. 数据库迁移 ==="
cd backend
export PYTHONPATH=$(pwd)
python manage.py migrate --noinput
python manage.py collectstatic --noinput
cd /data/workmind

echo "=== 3. 前端依赖与构建 ==="
cd frontend
if command -v yarn &>/dev/null; then
    yarn install --frozen-lockfile 2>/dev/null || yarn install
    yarn build
else
    npm ci 2>/dev/null || npm install
    npm run build
fi
cd /data/workmind

echo "=== 部署脚本执行完成 ==="
echo "请完成："
echo "  1. 配置 /data/workmind/.env（数据库、Redis、SECRET_KEY、ALLOWED_HOSTS 等）"
echo "  2. 复制 Nginx 配置：sudo cp /data/workmind/deployment/nginx/server.conf /etc/nginx/conf.d/workmind.conf"
echo "  3. 修改 workmind.conf 中的 server_name，然后 sudo nginx -t && sudo systemctl reload nginx"
echo "  4. 安装并启动 systemd 服务：sudo cp deployment/systemd/workmind.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable workmind && sudo systemctl start workmind"
echo "  5. 若 Nginx 运行用户不是 www-data，请修改 workmind.service 中的 User/Group"
