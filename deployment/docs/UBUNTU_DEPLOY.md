# Workmind Ubuntu 服务器部署文档（裸机 / systemd / Nginx）

适用场景：你准备把 Workmind 开源后，部署到 **Ubuntu 22.04/24.04 LTS** 服务器。  
默认代码目录：`/data/workmind`（可替换，但需要同步修改 Nginx 与 systemd 配置里的路径）。

本文档覆盖：

- 系统初始化与端口/防火墙
- 安装 Python/Node/MySQL/Redis/RabbitMQ/Nginx
- 配置 `.env`、数据库初始化与迁移
- 前端构建与静态资源
- systemd 常驻（后端 Daphne + Celery Beat/Worker）
- Nginx 反向代理 + WebSocket + HTTPS（Certbot）
- 日志与常见故障排查

> 说明：仓库内已提供可直接复用的模板  
> - Nginx：`deployment/nginx/server.conf`（默认监听 `8080`，后端端口 `8009`）  
> - systemd：`deployment/systemd/workmind.service`、`deployment/systemd/celery-*.service`

---

## 0. 规划与约定（建议先看）

- **系统**：Ubuntu 22.04/24.04
- **后端**：Django + Daphne（ASGI），监听 `0.0.0.0:8009`
- **前端**：`frontend/dist` 静态站点，由 Nginx 提供
- **静态资源**：Django `collectstatic` 输出到 `backend/static_root/`，通过 Nginx 暴露为 `/django_static/`
- **数据库**：MySQL 8.0
- **Redis**：channels-redis / 缓存
- **Celery（必装：完整功能）**：RabbitMQ 做 broker；Beat/Worker 用 systemd 常驻（智能体/用例生成等耗时任务建议走异步队列；定时任务依赖 Beat）

端口建议：

- **80/443**：Nginx（对外）
- **8009**：后端 Daphne（仅本机或内网访问；由 Nginx 反代）
- **3306**：MySQL（建议仅本机或内网）
- **6379**：Redis（建议仅本机或内网）
- **5672**：RabbitMQ（建议仅本机或内网）

---

## 1. 系统初始化

### 1.1 创建目录并克隆代码

```bash
sudo mkdir -p /data
sudo chown -R $USER:$USER /data

cd /data
git clone <你的仓库地址> workmind
cd /data/workmind
```

如果你使用了非 `/data/workmind` 目录，后文中涉及到的路径都要对应替换（尤其是 Nginx 与 systemd）。

### 1.2 基础更新与常用工具

```bash
sudo apt update
sudo apt -y upgrade
sudo apt -y install curl git vim unzip ca-certificates build-essential pkg-config
```

### 1.3 防火墙（可选但强烈建议）

若你使用 UFW：

```bash
sudo apt -y install ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 2. 安装运行时依赖

### 2.1 安装 Python 3.11+

Ubuntu 22.04/24.04 默认 Python 版本足够（不必强行装 3.9）。安装 venv 与开发头文件：

```bash
sudo apt -y install python3 python3-venv python3-dev
```

### 2.2 安装 Node.js 18+

建议使用 NodeSource 安装 Node 18（与仓库文档一致）。

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt -y install nodejs

node -v
npm -v
```

若你希望使用 Node 20 也可以，但需确保前端构建无兼容问题。

### 2.3 安装 Nginx

```bash
sudo apt -y install nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 2.4 安装 MySQL

```bash
sudo apt -y install mysql-server
sudo systemctl enable mysql
sudo systemctl start mysql
```

建议运行一次安全向导（可选）：

```bash
sudo mysql_secure_installation
```

### 2.5 安装 Redis

```bash
sudo apt -y install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 2.6 安装 RabbitMQ（必装：完整功能需要）

为部署完整功能（异步任务 + 定时任务 + 智能体/用例生成等耗时任务），安装 RabbitMQ：

```bash
sudo apt -y install rabbitmq-server
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server
```

---

## 3. MySQL 建库建用户

你可以用两种方式：

- **方式 A（更推荐）**：创建专用用户（最安全）
- **方式 B**：直接使用 MySQL `root`（简单但不推荐）

### 3.1 方式 A：创建数据库与专用用户（推荐）

进入 MySQL：

```bash
sudo mysql
```

执行（把密码替换掉）：

```sql
CREATE DATABASE IF NOT EXISTS workmind DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'workmind'@'localhost' IDENTIFIED BY '请替换为强密码';
GRANT ALL PRIVILEGES ON workmind.* TO 'workmind'@'localhost';
FLUSH PRIVILEGES;
```

退出：

```sql
EXIT;
```

### 3.2 方式 B：使用 root（不推荐）

仅创建库：

```bash
sudo mysql -e "CREATE DATABASE IF NOT EXISTS workmind DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

---

## 4. 配置项目环境变量（.env）

在项目根目录创建 `.env`（仓库提供 `.env.example`）：

```bash
cd /data/workmind
cp .env.example .env
vim .env
```

生产环境**必须**修改项（最少）：

- `DATABASE_HOST` / `DATABASE_USER` / `DATABASE_PASSWORD` / `DATABASE_NAME`
- `SECRET_KEY`：换成随机长字符串
- `DEBUG=False`
- `ALLOWED_HOSTS=你的域名或服务器IP`

若启用 Celery（RabbitMQ）：

- `MQ_HOST` / `MQ_USER` / `MQ_PASSWORD`

Redis 若本机无密码通常保持默认即可：

- `REDIS_HOST=127.0.0.1`
- `REDIS_PORT=6379`

> 后端会从项目根目录加载 `.env`（systemd 服务同样引用了 `/data/workmind/.env`）。

---

## 5. 后端部署（Django + Daphne）

### 5.1 安装系统级依赖（mysqlclient 编译所需）

你的依赖里包含 `mysqlclient`，Ubuntu 需要安装 MySQL 开发库：

```bash
sudo apt -y install default-libmysqlclient-dev
```

如遇到编译相关报错，也可补充：

```bash
sudo apt -y install libffi-dev libssl-dev
```

### 5.2 创建 venv 并安装 Python 依赖

```bash
cd /data/workmind

python3 -m venv backend/venv
source backend/venv/bin/activate

python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 5.3 迁移数据库与收集静态文件

```bash
cd /data/workmind/backend
export PYTHONPATH=$(pwd)

python manage.py migrate
python manage.py collectstatic --noinput

# 可选：创建管理员
python manage.py createsuperuser
```

### 5.4 本机快速验证（可选）

在 venv 内直接起 daphne 测试：

```bash
cd /data/workmind/backend
source venv/bin/activate
export PYTHONPATH=$(pwd)

daphne -b 0.0.0.0 -p 8009 backend.asgi:application
```

新开一个终端测试：

```bash
curl -I http://127.0.0.1:8009/admin/
```

确认没问题后停止 daphne（Ctrl+C），进入 systemd 部署。

---

## 6. 前端构建

```bash
cd /data/workmind/frontend
npm install
npm run build
```

构建产物在 `frontend/dist/`，后续由 Nginx 直接对外提供。

若 npm 很慢，可设置镜像（可选）：

```bash
npm config set registry https://registry.npmmirror.com
```

---

## 7. Nginx 配置（HTTP）

仓库提供了裸机部署模板：`deployment/nginx/server.conf`，默认监听 `8080`。  
如果你希望直接用 `80`，请按下文“7.3 使用 80 端口（推荐）”修改。

### 7.1 安装配置文件

```bash
sudo cp /data/workmind/deployment/nginx/server.conf /etc/nginx/conf.d/workmind.conf
```

### 7.2 修改关键项

编辑：

```bash
sudo vim /etc/nginx/conf.d/workmind.conf
```

确认/修改以下字段与路径（模板默认值如下）：

- `server_name _;`：改为你的域名或服务器 IP
- 前端：`root /data/workmind/frontend/dist;`
- Django 静态：`alias /data/workmind/backend/static_root/;`
- 反代后端：`proxy_pass http://127.0.0.1:8009/...;`
- WebSocket：`location /ws/ { ... proxy_http_version 1.1; Upgrade/Connection ... }`

### 7.3 使用 80 端口（推荐）

若你这台机器只部署 Workmind（或者你愿意让它占用 80），建议把：

- `listen 8080;` 改为 `listen 80;`

然后：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 8. systemd 常驻运行后端（workmind.service）

仓库已提供：`deployment/systemd/workmind.service`，默认：

- `WorkingDirectory=/data/workmind/backend`
- `EnvironmentFile=/data/workmind/.env`
- `ExecStart=... daphne ... -p 8009 backend.asgi:application`

### 8.1 安装并启动服务

```bash
sudo cp /data/workmind/deployment/systemd/workmind.service /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable workmind
sudo systemctl start workmind
sudo systemctl status workmind
```

查看日志：

```bash
journalctl -u workmind -f
```

### 8.2 健康检查

确认后端监听：

```bash
ss -tlnp | grep 8009
curl -I http://127.0.0.1:8009/admin/
```

确认 Nginx 转发（根据你 listen 的端口）：

```bash
curl -I http://127.0.0.1/
# 或
curl -I http://127.0.0.1:8080/
```

---

## 9. Celery（必装：定时任务与异步任务）

为部署完整功能（智能体/用例生成、UI 测试等耗时任务 + “提测/测试延期标签同步”等定时任务），需要启用 Celery（Beat + Worker）。

前置要求：

- MySQL、Redis、RabbitMQ 可用
- `.env` 中已配置 RabbitMQ（`MQ_*`）

### 9.1 首次部署：写入定时任务配置

首次部署或修改执行时间时，在 venv 环境里执行一次：

```bash
cd /data/workmind/backend
source venv/bin/activate
export PYTHONPATH=$(pwd)

python manage.py setup_delayed_tag_beat
```

### 9.2 安装并启动 Celery Worker / Beat

```bash
sudo cp /data/workmind/deployment/systemd/celery-worker.service /etc/systemd/system/
sudo cp /data/workmind/deployment/systemd/celery-beat.service /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat
sudo systemctl status celery-worker celery-beat
```

日志：

```bash
journalctl -u celery-worker -f
journalctl -u celery-beat -f
```

修改了定时任务时间后，记得重启 Beat：

```bash
sudo systemctl restart celery-beat
```

---

## 10. HTTPS（Certbot / Let’s Encrypt，推荐）

前提：

- 你有域名解析到服务器公网 IP
- 80 端口对外可访问（Let’s Encrypt 需要 HTTP-01 校验）

### 10.1 安装 Certbot（Nginx 插件）

```bash
sudo apt update
sudo apt -y install certbot python3-certbot-nginx
```

### 10.2 申请证书并自动改 Nginx 配置

把 `<your-domain.com>` 换成你的域名：

```bash
sudo certbot --nginx -d <your-domain.com>
```

按提示选择：

- 自动跳转到 HTTPS（推荐）

### 10.3 自动续期验证

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

---

## 11. 发布/升级流程（建议）

典型升级步骤：

```bash
cd /data/workmind
git pull

# 后端
source backend/venv/bin/activate
pip install -r backend/requirements.txt
cd backend
export PYTHONPATH=$(pwd)
python manage.py migrate
python manage.py collectstatic --noinput
deactivate

# 前端
cd /data/workmind/frontend
npm install
npm run build

# 重启服务
sudo systemctl restart workmind
sudo systemctl restart nginx

# 若启用 celery
sudo systemctl restart celery-worker celery-beat
```

---

## 12. 日志与常见故障排查

### 12.1 查看服务状态与日志

```bash
sudo systemctl status workmind
sudo journalctl -u workmind -n 200 --no-pager

sudo systemctl status nginx
sudo journalctl -u nginx -n 200 --no-pager
```

若启用 Celery：

```bash
sudo systemctl status celery-worker celery-beat
sudo journalctl -u celery-worker -n 200 --no-pager
sudo journalctl -u celery-beat -n 200 --no-pager
```

### 12.2 502 Bad Gateway（最常见）

- 确认后端是否在监听 `8009`：

```bash
ss -tlnp | grep 8009
```

- 看后端日志：

```bash
journalctl -u workmind -f
```

- 检查 Nginx 反代地址是否仍是 `127.0.0.1:8009`

### 12.3 静态资源 404

- 确认执行过：

```bash
cd /data/workmind/backend
source venv/bin/activate
export PYTHONPATH=$(pwd)
python manage.py collectstatic --noinput
```

- 确认 Nginx 中 `alias` 指向：
  - `/data/workmind/backend/static_root/`

### 12.4 WebSocket 连接失败

确认 Nginx `/ws/` 段包含（模板已包含）：

- `proxy_http_version 1.1`
- `proxy_set_header Upgrade $http_upgrade;`
- `proxy_set_header Connection "upgrade";`

### 12.5 Celery 定时任务不执行

- Beat 与 Worker 都要运行：

```bash
systemctl status celery-beat celery-worker
```

- 修改执行时间后要重启 Beat：

```bash
sudo systemctl restart celery-beat
```

- 首次部署别忘了执行一次：

```bash
python manage.py setup_delayed_tag_beat
```

---

## 13. 最终验收清单

- 能打开前端页面：`http(s)://你的域名或IP`
- `/admin/` 能访问（登录正常）
- `/api/` 请求正常（无 502/500）
- 有 WebSocket 的功能正常（例如页面实时功能，不报 ws 连接错误）
- Celery Beat/Worker 正常运行，日志无持续报错（完整功能必需）

