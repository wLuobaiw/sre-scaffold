#!/bin/bash
# sre-scaffold entrypoint —— 启动前校验，缺少必要参数时打印帮助并退出

set -e

# ── 校验 toolkit 是否已挂载 ──────────────────────────────────
TOOLKIT_DIR="/app/toolkit"
ANSIBLE_ROLES="${TOOLKIT_DIR}/ansible/roles"

if [ ! -d "$ANSIBLE_ROLES" ] || [ -z "$(ls -A "$ANSIBLE_ROLES" 2>/dev/null)" ]; then
    cat <<EOF
┌─────────────────────────────────────────────────────────────┐
│                     sre-scaffold                           │
│              自动化部署工具 · 四步向导 Web 界面               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  使用方式:                                                  │
│                                                             │
│  1. 一键安装（推荐）                                        │
│     curl -sSL <url>/install.sh | bash                       │
│                                                             │
│  2. 手动运行                                                │
│     docker run -d \\                                        │
│       -p 5000:5000 \\                                       │
│       -v /path/to/toolkit:/app/toolkit \\                    │
│       --name sre-scaffold \\                                │
│       sre-scaffold:latest                                   │
│                                                             │
│  3. 开发模式（挂载源码 + toolkit）                          │
│     docker run -d \\                                        │
│       -p 5000:5000 \\                                       │
│       -v \$(pwd)/scaffold/web:/app/web \\                     │
│       -v \$(pwd)/toolkit:/app/toolkit \\                     │
│       sre-scaffold:latest                                   │
│                                                             │
│  必要条件:                                                  │
│    · toolkit 目录必须挂载到 /app/toolkit                     │
│    · toolkit/ansible/roles/ 下需有可部署的组件物料           │
│                                                             │
│  物料目录结构:                                              │
│    toolkit/                                                 │
│    └── ansible/                                             │
│        └── roles/                                           │
│            ├── middleware/                                  │
│            │   ├── mysql/8.0/   (conf.yaml + tasks/)       │
│            │   └── redis/7.4/                               │
│            └── system/                                      │
│                └── linux-init/1.0.0/                        │
│                                                             │
│  环境变量:                                                  │
│    MATERIALS_LOCAL_PATH  物料路径（默认 /app/toolkit）       │
│    FLASK_PORT            Web 端口（默认 5000）              │
│    DEBUG                 调试模式（默认 true）              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
EOF
    exit 1
fi

# ── 正常启动 ────────────────────────────────────────────────
echo "[sre-scaffold] toolkit 已挂载: ${TOOLKIT_DIR}"
echo "[sre-scaffold] 启动 Web 服务..."

exec python web/app.py
