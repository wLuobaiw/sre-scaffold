# =======================阶段一（构建）=======================
# 构建 python 镜像，用于构建前后端
FROM python:3.12-slim AS builder

# 复制依赖文件
COPY web/requirements.txt .

# 安装依赖，使用国内镜像源
RUN pip install --no-cache-dir \
    --prefix=/install \
    -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple



# =======================阶段二（运行）=======================
FROM python:3.12-slim

WORKDIR /app

# 从构建阶段复制已安装的 Python 包
COPY --from=builder /install /usr/local

# 安装必要的工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

# 预留挂载点 —— web/ 和 toolkit/ 在运行时通过 -v 挂载
RUN mkdir -p /app/web

EXPOSE 5000

CMD ["python", "web/app.py"]