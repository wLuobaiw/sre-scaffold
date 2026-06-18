#!/bin/bash
set -e

# ── 配置 ──────────────────────────────────────────────────────
IMAGE_NAME="${1:-sre-scaffold:latest}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 颜色 ──────────────────────────────────────────────────────
GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[BUILD]${NC} $*"; }

# ── 构建 ──────────────────────────────────────────────────────
info "镜像: ${IMAGE_NAME}"
info "上下文: ${SCRIPT_DIR}"
info "开始构建..."

docker build -t "${IMAGE_NAME}" "${SCRIPT_DIR}"

info "构建完成: ${IMAGE_NAME}"
docker image inspect "${IMAGE_NAME}" --format '  大小: {{.Size}} | 创建: {{.Created}}'
