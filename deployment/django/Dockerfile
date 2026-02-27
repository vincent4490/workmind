FROM python:3.9-slim-bookworm as Base
WORKDIR /backend
COPY ./backend/requirements_linux.txt requirements.txt

# 国内打包请替换成 https://mirrors.aliyun.com/pypi/simple
#https://pypi.org/simple
ARG PIP_INDEX_URL="https://mirrors.aliyun.com/pypi/simple"
# 安装依赖，尽量减少镜像层并在安装后清理
RUN echo 'deb http://mirrors.aliyun.com/debian/ bookworm main non-free-firmware contrib' > /etc/apt/sources.list && \
    echo 'deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free' >> /etc/apt/sources.list && \
    echo 'deb http://mirrors.aliyun.com/debian/ bookworm-updates main non-free-firmware contrib' >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends default-libmysqlclient-dev build-essential libpcre3-dev && \
    pip install --no-cache-dir -r requirements.txt -i ${PIP_INDEX_URL} && \
    apt-get remove -y build-essential libpcre3-dev && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 第二阶段开始
FROM python:3.9-slim-bookworm

# 设置时区并安装 ADB
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main non-free non-free-firmware contrib" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y default-libmysqlclient-dev tzdata adb && \
    echo "Asia/Shanghai" > /etc/timezone && \
    ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 从构建阶段复制安装的包
COPY --from=Base /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=Base /usr/local/bin /usr/local/bin

# 复制应用代码
WORKDIR /backend
COPY ./backend .
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "120"]
