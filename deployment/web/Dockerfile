# ===== 构建阶段 =====
FROM node:20-alpine AS build
WORKDIR /web

# 安装 curl 解决 HTTP2 问题
RUN apk add --no-cache curl \
    && echo "network-timeout 300000" > ~/.npmrc \
    && echo "registry=https://registry.npmmirror.com" > ~/.npmrc
# 设置 Yarn 镜像源
RUN yarn config set registry https://registry.npmmirror.com \
    && yarn config set disturl https://npmmirror.com/mirrors/node \
    && yarn config set sass_binary_site https://npmmirror.com/mirrors/node-sass

# 先复制依赖文件，利用缓存
COPY frontend/package.json frontend/yarn.lock ./

# 安装依赖（增加超时和重试）
RUN yarn install --frozen-lockfile --network-timeout 600000 --registry=https://registry.npmmirror.com

# 再复制源码
COPY frontend .

# 构建前端
RUN yarn build

# ===== 运行阶段 =====
FROM nginx:1.21-alpine
WORKDIR /usr/share/nginx/html

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制 nginx 配置
COPY ./deployment/web/nginx.conf /etc/nginx/conf.d/workmind.conf

# 复制静态资源
COPY ./backend/static_root /www/workmind/static

# 从构建阶段复制前端产物
COPY --from=build /web/dist .

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

