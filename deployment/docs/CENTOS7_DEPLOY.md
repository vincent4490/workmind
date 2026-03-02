# Workmind 在 CentOS 7 上的部署步骤

代码目录：`/data/workmind`。以下命令均在 root 或加 `sudo` 执行。

---

## 一、安装基础依赖（EPEL、Nginx、Redis 等）

```bash
# EPEL 源（很多包依赖它）
yum install -y epel-release

# Nginx、Redis、编译工具、开发库
yum install -y nginx redis gcc gcc-c++ make openssl-devel bzip2-devel libffi-devel zlib-devel
systemctl enable nginx redis
systemctl start redis
```

---

## 二、安装 Python 3.9（CentOS 7 默认只有 3.6）

### 方式 A：用 IUS 源（推荐）

```bash
yum install -y https://repo.ius.io/ius-release-el7.rpm
yum install -y python39 python39-pip python39-devel

# 确认版本
python3.9 --version   # 应为 3.9.x
```

### 方式 B：若 IUS 不可用，从源码安装

```bash
yum install -y gcc make openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel
cd /tmp
curl -O https://www.python.org/ftp/python/3.9.18/Python-3.9.18.tgz
tar -xzf Python-3.9.18.tgz && cd Python-3.9.18
./configure --enable-optimizations --prefix=/usr/local
make -j$(nproc) && make altinstall
ln -sf /usr/local/bin/python3.9 /usr/local/bin/python3.9
cd /tmp && rm -rf Python-3.9.18*
# 之后用 /usr/local/bin/python3.9
```

---

## 三、安装 Node.js 18（CentOS 7 自带的太旧）

```bash
curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
yum install -y nodejs
node -v   # 应为 v18.x
npm -v
```

若上述源较慢，可用国内镜像：

```bash
curl -fsSL https://rpm.nodesource.com/setup_18.x | sed 's|rpm.nodesource.com|mirrors.tuna.tsinghua.edu.cn/nodesource/rpm_18.x|g' | bash -
yum install -y nodejs
```

---

## 四、安装 MySQL 并建库（使用 root 账号）

若已安装 MySQL 且使用 **root** 账号连接，只需创建数据库即可（无需新建用户）。

```bash
# 若尚未安装 MySQL，可从官网下载 CentOS 7 的 repo 安装 5.7/8.0，或使用 MariaDB：
# yum install -y mariadb-server mariadb-devel
# systemctl enable mariadb && systemctl start mariadb

# 使用 root 登录，只创建 workmind 库（密码在提示时输入）
mysql -u root -p -e "
CREATE DATABASE IF NOT EXISTS workmind DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"
```

**.env 中配置**：`DATABASE_USER=root`，`DATABASE_PASSWORD=你的root密码`，`DATABASE_NAME=workmind`。

---

## 五、配置项目环境变量

```bash
cd /data/workmind
cp .env.example .env
vim .env
```

必改项（使用 MySQL root 时）：

- `DATABASE_HOST=localhost`（本机填 localhost）
- `DATABASE_USER=root`
- `DATABASE_PASSWORD=你的MySQL的root密码`
- `DATABASE_NAME=workmind`
- `SECRET_KEY=随机长字符串`（生产务必换掉示例值）
- `DEBUG=False`
- `ALLOWED_HOSTS=服务器IP或域名`（如 `172.13.6.230`）
- Redis 在本机且无密码可保持：`REDIS_HOST=127.0.0.1`，`REDIS_PORT=6379`

---

## 六、后端：虚拟环境、依赖、迁移、静态文件

```bash
cd /data/workmind

# 若 Python 3.9 命令是 python3.9（IUS 安装）
python3.9 -m venv backend/venv
# 若在 /usr/local（源码安装）
# /usr/local/bin/python3.9 -m venv backend/venv

source backend/venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

cd backend
export PYTHONPATH=$(pwd)
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser   # 可选
deactivate
cd /data/workmind
```

若安装依赖时报错缺少 MySQL 相关头文件，请安装：`yum install -y mysql-devel`（官方 MySQL）或 `yum install -y mariadb-devel`（MariaDB）。

---

## 七、前端构建

```bash
cd /data/workmind/frontend
npm install
npm run build
cd /data/workmind
```

若 npm 很慢，可先设国内镜像：`npm config set registry https://registry.npmmirror.com`

---

## 八、Nginx 配置（CentOS 用 nginx 用户）

```bash
cp /data/workmind/deployment/nginx/server.conf /etc/nginx/conf.d/workmind.conf
vim /etc/nginx/conf.d/workmind.conf
```

修改：

- `server_name _;` 改为你的 IP 或域名，例如：`server_name 172.13.6.230;`
- 确认 `root` 为 `/data/workmind/frontend/dist`，`alias` 为 `/data/workmind/backend/static_root/`，`proxy_pass` 为 `http://127.0.0.1:8009`。若使用 8080 端口，访问地址为 `http://IP:8080`

然后：

```bash
nginx -t
systemctl reload nginx
```

---

## 九、Systemd 运行后端

模板默认以 **root** 运行（省去 ADB/目录权限配置），直接复制并启动即可：

```bash
cp /data/workmind/deployment/systemd/workmind.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable workmind
systemctl start workmind
systemctl status workmind
```

查看日志：`journalctl -u workmind -f`

**设备管理 / ADB**：刷新设备列表依赖系统上的 `adb`。模板里 `PATH` 已包含 `/usr/local/bin:/usr/bin:/bin`，root 下 ADB 可直接用。若仍报“未检测到可用 ADB 路径”，可在 Django 后台 **UI测试配置**（表 `ui_test_config`）里将 **ADB路径** 设为绝对路径，如 `/usr/bin/adb` 或 `/opt/android-sdk/platform-tools/adb`。

**可选：改为 nginx 用户（生产建议）**  
若希望后端与 Nginx 同用 `nginx` 用户，编辑 service 将 `User=root`、`Group=root` 改为 `User=nginx`、`Group=nginx`，并执行：

```bash
chown -R nginx:nginx /data/workmind
mkdir -p /data/workmind/backend/.adb_home
chown nginx:nginx /data/workmind/backend/.adb_home
```


---

## 十、检查与访问

```bash
ss -tlnp | grep 8009   # 应有 daphne 监听
curl -I http://127.0.0.1:8009/admin/   # 本机测后端
curl -I http://172.13.6.230/   # 用你实际 IP 测 Nginx
```

浏览器访问：`http://172.13.6.230` 或 `http://172.13.6.230:8080`（若 Nginx 使用 8080 端口），应能打开登录页。

---

## 常见问题（CentOS 7）

- **python3.9: command not found**  
  用 IUS 装：`yum install -y python39`；或源码安装后使用绝对路径 `/usr/local/bin/python3.9` 创建 venv。

- **pip install 报错 mysqlclient / MySQLdb**  
  安装：`yum install -y mariadb-devel`（或 `mysql-devel`），再重装依赖。

- **502 Bad Gateway**  
  查后端是否起来：`systemctl status workmind`、`ss -tlnp | grep 8009`；查日志：`journalctl -u workmind -n 50`。若权限问题，检查 `User/Group` 与目录归属。

- **静态 404**  
  确认执行过 `python manage.py collectstatic`，且 Nginx 里 `alias` 指向 `/data/workmind/backend/static_root/`。

- **SELinux 拦截**  
  可先临时关闭测试：`setenforce 0`。长期可对 Nginx 放行网络、文件访问：  
  `setsebool -P httpd_can_network_connect 1`，或按需配置 Nginx 相关 context。

- **刷新设备列表报 500 / 未检测到可用 ADB 路径**  
  systemd 里原 `PATH` 只有 venv，进程找不到 `adb`。请更新为仓库里的 `workmind.service`（已含 `PATH=.../venv/bin:/usr/local/bin:/usr/bin:/bin`），执行 `systemctl daemon-reload && systemctl restart workmind`。若仍不行，在 Django 后台 **UI测试配置** 中把 **ADB路径** 设为绝对路径，如 `/usr/bin/adb`。

- **刷新设备列表报「failed to start daemon adb」「Permission denied」**  
  若改用 **nginx** 用户跑后端，需为 ADB 提供可写目录：在 service 中增加 `Environment="HOME=/data/workmind/backend/.adb_home"`，并在服务器执行 `mkdir -p /data/workmind/backend/.adb_home && chown nginx:nginx /data/workmind/backend/.adb_home`，然后 `systemctl restart workmind`。默认以 root 运行则无此问题。
