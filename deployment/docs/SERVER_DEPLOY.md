# Workmind 服务器部署说明（/data/workmind）

适用于已将代码克隆到服务器 `/data/workmind` 的裸机部署（非 Docker）。

**CentOS 7 用户请直接看：[CENTOS7_DEPLOY.md](./CENTOS7_DEPLOY.md)**（含 Python 3.9、Node 18、MariaDB、nginx 用户等说明）。

## 一、环境要求

- **系统**：Linux（如 CentOS 7+、Ubuntu 20.04+）
- **Python**：3.9+
- **Node.js**：18+（用于构建前端）
- **MySQL**：5.7+ 或 8.0
- **Redis**：6+
- **RabbitMQ**：3.x（Celery 消息队列，若不用异步任务可后续再装）
- **Nginx**：作为反向代理与静态资源服务

## 二、安装基础服务（若未安装）

```bash
# CentOS 示例
sudo yum install -y python39 python39-devel nodejs npm nginx mysql redis

# Ubuntu 示例
sudo apt update
sudo apt install -y python3.9 python3.9-venv python3.9-dev nodejs npm nginx mysql-server redis-server
```

MySQL / RabbitMQ 需单独安装并创建数据库与用户，Redis 默认无密码即可。

## 三、项目目录与环境变量

代码已克隆到 `/data/workmind`。

1. **创建并配置 `.env`**（在项目根目录 `/data/workmind`）：

```bash
cd /data/workmind
cp .env.example .env
vim .env   # 按实际修改数据库、Redis、RabbitMQ、SECRET_KEY、ALLOWED_HOSTS 等
```

必改项示例：

- `DATABASE_HOST`、`DATABASE_USER`、`DATABASE_PASSWORD`、`DATABASE_NAME`
- `REDIS_HOST`、`REDIS_PORT`（若 Redis 有密码则填 `REDIS_PASSWORD`）
- `MQ_HOST`、`MQ_USER`、`MQ_PASSWORD`（若使用 Celery）
- `SECRET_KEY`（生产环境务必换新）
- `DEBUG=False`
- `ALLOWED_HOSTS=你的域名或服务器IP`

2. **确认后端能读到 `.env`**：`backend/conf/env.py` 会加载项目根目录的 `.env`，无需额外操作。

## 四、后端部署

```bash
cd /data/workmind

# 1. 创建虚拟环境并安装依赖
python3.9 -m venv backend/venv
source backend/venv/bin/activate   # Linux
# Windows: backend\venv\Scripts\activate

pip install -r backend/requirements.txt
# 生产环境建议加：gunicorn（若只用 daphne 可省略）

# 2. 数据库迁移
cd backend
export PYTHONPATH=$(pwd)
python manage.py migrate

# 3. 收集静态文件（Django 后台等）
python manage.py collectstatic --noinput

# 4. 可选：创建超级用户
python manage.py createsuperuser
```

后端通过 **Daphne**（ASGI）同时提供 HTTP 与 WebSocket，无需单独起 gunicorn。

## 五、前端构建

```bash
cd /data/workmind/frontend

# 使用 npm 或 yarn（二选一）
npm install
npm run build

# 或
yarn install
yarn build
```

构建产物在 `frontend/dist/`，由 Nginx 对外提供。

## 六、Nginx 配置

1. 将仓库中的示例配置复制到 Nginx：

```bash
sudo cp /data/workmind/deployment/nginx/server.conf /etc/nginx/conf.d/workmind.conf
```

2. 编辑 `/etc/nginx/conf.d/workmind.conf`，确认/修改：

- `server_name` 为你的域名或 IP
- `root` 指向 `/data/workmind/frontend/dist`
- `alias` 的静态目录指向 `/data/workmind/backend/static_root`
- `proxy_pass` 指向 `http://127.0.0.1:8009`（与后面 systemd 端口一致）

3. 检查配置并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 七、使用 Systemd 运行后端

1. 安装服务文件：

```bash
sudo cp /data/workmind/deployment/systemd/workmind.service /etc/systemd/system/
# 确认 ExecStart 中的路径为 /data/workmind
sudo systemctl daemon-reload
```

2. 启动并设置开机自启：

```bash
sudo systemctl enable workmind
sudo systemctl start workmind
sudo systemctl status workmind
```

日志：`journalctl -u workmind -f`

## 八、一键部署脚本（可选）

在服务器上执行：

```bash
cd /data/workmind
chmod +x deployment/scripts/deploy.sh
./deployment/scripts/deploy.sh
```

脚本会：创建 venv、安装后端依赖、执行 migrate、collectstatic、安装前端依赖并 build。**不会**自动配置 Nginx 或 systemd，需按第六、七步手动完成。

## 九、目录与权限

- 确保 Nginx 运行用户对以下目录有读权限：  
  `/data/workmind/frontend/dist`、`/data/workmind/backend/static_root`
- 若使用上传/导出功能，确保应用对 `backend/apps/ai_testcase/output`、`backend/apps/ai_testcase/uploads` 有写权限。

## 十、常见问题

- **502 Bad Gateway**：检查 Daphne 是否在 8009 端口监听：`ss -tlnp | grep 8009`，并查看 `journalctl -u workmind`。
- **静态 404**：确认已执行 `collectstatic`，且 Nginx 中 `alias`/`root` 路径正确。
- **WebSocket 连不上**：确认 Nginx 中 `/ws/` 已按示例配置了 `proxy_http_version 1.1` 与 `Upgrade`、`Connection`。
- **跨域**：后端已使用 `django-cors-headers`，生产环境建议在 `ALLOWED_HOSTS` 和 Nginx 中限定域名，不要用 `*`。

部署完成后，访问 `http://你的域名或IP` 即可使用前端；API 与 WebSocket 通过同一 Nginx 转发到后端 8009 端口。
