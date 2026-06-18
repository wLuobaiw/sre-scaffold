# ===================== 阶段一：构建依赖 =====================
FROM python:3.12-slim AS builder

COPY web/requirements.txt .
RUN pip install --no-cache-dir \
    --prefix=/install \
    -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple


# ===================== 阶段二：运行镜像 =====================
FROM python:3.12-slim

WORKDIR /app

# 系统工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    git \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制 Python 包
COPY --from=builder /install /usr/local

# 将 scaffold/ 下所有文件打包进镜像
COPY . .

# SSH 配置 + toolkit 挂载点
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh
RUN mkdir -p /app/toolkit

# entrypoint —— 启动前校验挂载，缺少参数时打印帮助并退出
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
