# WorkMind 

## 技术栈

### 后端
- Django 4.2.7
- Django REST Framework
- Celery (异步任务)
- MySQL (数据库)
- Redis (缓存)
- RabbitMQ (消息队列)
- EasyOCR + Airtest (UI 自动化)
- OpenAI (AI 测试用例生成)

### 前端
- Vue 3.3
- Element Plus
- Vite
- Vuex
- Vue Router
- Monaco Editor (代码编辑器)

## 环境要求

- Python 3.8+
- Node.js 6.0+ / npm 3.0+
- MySQL 5.7+
- Redis 6.0+
- RabbitMQ 3.8+

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. 配置环境变量

复制环境变量模板并修改配置：

```bash
copy .env.example .env
```

编辑 `.env` 文件，填写以下必要配置：

```env
# MySQL 数据库
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_USER=root
DATABASE_PASSWORD=你的MySQL密码
DATABASE_NAME=workmind

# RabbitMQ
MQ_USER=guest
MQ_PASSWORD=guest
MQ_HOST=127.0.0.1
MQ_PORT=5672

# Redis
REDIS_ON=True
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=
REDIS_PORT=6379
REDIS_DB=0

# Django
SECRET_KEY=你的随机密钥
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Kimi AI 配置（用于 AI 测试用例生成）
KIMI_API_KEY=你的Kimi API Key
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.5
```

如何获取 Kimi API Key：
1. 访问 [Moonshot AI 开放平台](https://platform.moonshot.cn/)
2. 注册并登录账号
3. 在控制台创建 API Key
4. 将 API Key 填入 `.env` 文件的 `KIMI_API_KEY` 配置项

### 3. 创建 Python 虚拟环境

推荐使用虚拟环境隔离项目依赖，在项目根目录下执行：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 激活虚拟环境 (Linux/Mac)
source venv/bin/activate
```

激活后，命令行前面会显示 `(venv)` 标识。后续的 pip 安装命令都需要在激活虚拟环境后执行。

### 4. 创建数据库

在安装依赖之前，需要先创建 MySQL 数据库：

```bash
# 登录 MySQL
mysql -u root -p

# 创建数据库
CREATE DATABASE workmind CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 退出 MySQL
exit;
```

### 5. 安装依赖

#### 后端依赖

```bash
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 前端依赖

```bash
cd frontend
npm install
```

### 6. 初始化数据库

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 7. 启动服务

#### 启动后端服务 (Django)

```bash
cd backend
python manage.py runserver 0.0.0.0:8009
```

#### 启动前端服务 (Vue)

```bash
cd frontend
npm run dev
```

前端默认运行在 `http://localhost:8888`

#### 启动 Celery Worker (可选)

如果需要使用异步任务功能：

```bash
cd backend
celery -A backend worker -l info
```

#### 启动 Celery Beat (可选)

如果需要使用定时任务功能：

```bash
cd backend
celery -A backend beat -l info
```

### 8. 访问应用

- 前端地址: http://localhost:8888
- 后端 API: http://localhost:8009
- Django Admin: http://localhost:8009/admin

## 停止服务

在 Windows 环境下，可以使用提供的脚本停止所有服务：

```powershell
.\stop_services.ps1
```

## 项目结构

```
.
├── backend/              # Django 后端
│   ├── apps/            # 应用模块
│   │   ├── ai_testcase/ # AI 测试用例
│   │   ├── schema/      # 数据模型
│   │   ├── ui_test/     # UI 测试
│   │   └── workminduser/# 用户管理
│   ├── backend/         # 项目配置
│   ├── conf/            # 配置文件
│   ├── scripts/         # 脚本文件
│   └── manage.py        # Django 管理脚本
├── frontend/            # Vue3 前端
│   ├── src/            # 源代码
│   ├── static/         # 静态资源
│   └── package.json    # 依赖配置
├── deployment/          # 部署配置
│   ├── nginx/          # Nginx 配置
│   ├── mysql/          # MySQL 配置
│   └── ...
└── .env                # 环境变量配置
```

## 开发指南

### 后端开发

- 使用 Django REST Framework 开发 API
- 遵循 Django 项目结构规范
- 使用 pytest 进行单元测试

### 前端开发

- 使用 Vue 3 Composition API
- 遵循 Element Plus 组件库规范
- 使用 Vite 进行构建

## 生产部署

生产环境部署时，请注意：

1. 修改 `.env` 中的 `DEBUG=False`
2. 更换 `SECRET_KEY` 为随机密钥
3. 配置 `ALLOWED_HOSTS` 为实际域名或 IP
4. 使用 Nginx 作为反向代理
5. 使用 Gunicorn 或 uWSGI 运行 Django
6. 配置 SSL 证书启用 HTTPS

详细部署配置请参考 `deployment/` 目录。

## 常见问题

### 数据库连接失败

检查 MySQL 服务是否启动，以及 `.env` 中的数据库配置是否正确。

### 前端无法访问后端 API

检查后端服务是否正常运行，以及 CORS 配置是否正确。

### Celery 任务不执行

确保 Redis 和 RabbitMQ 服务正常运行，并检查 Celery Worker 是否启动。

## 许可证

[请根据实际情况添加许可证信息]

## 联系方式

[请根据实际情况添加联系方式]
