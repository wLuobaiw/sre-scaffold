#!/bin/bash
set -e

# ── 配置 ──────────────────────────────────────────────────────
FLASK_PORT="${FLASK_PORT:-5000}"
IMAGE_NAME="${IMAGE_NAME:-sre-scaffold:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-sre-scaffold}"
DOCKER_VERSION="${DOCKER_VERSION:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_SCRIPT="${SCRIPT_DIR}/scaffold/build.sh"

# ── 颜色 ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 检测操作系统 ──────────────────────────────────────────────
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"
    elif [ -f /etc/redhat-release ]; then
        OS_ID="rhel"
    else
        error "无法识别操作系统"
        exit 1
    fi
}

# ── 安装 Docker ──────────────────────────────────────────────
install_docker() {
    detect_os

    case "$OS_ID" in
        ubuntu|debian)
            info "检测到 ${OS_ID}，安装 Docker..."
            apt-get update
            apt-get install -y ca-certificates curl
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL "https://download.docker.com/linux/${OS_ID}/gpg" \
                -o /etc/apt/keyrings/docker.asc
            chmod a+r /etc/apt/keyrings/docker.asc
            echo "deb [arch=$(dpkg --print-architecture) \
                signed-by=/etc/apt/keyrings/docker.asc] \
                https://download.docker.com/linux/${OS_ID} \
                $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
                > /etc/apt/sources.list.d/docker.list
            apt-get update
            if [ -n "$DOCKER_VERSION" ]; then
                PKG="docker-ce=5:${DOCKER_VERSION}-*"
            else
                PKG="docker-ce"
            fi
            apt-get install -y ${PKG} docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
        centos|rhel|rocky|alma|fedora)
            info "检测到 ${OS_ID}，安装 Docker..."
            yum install -y yum-utils
            yum-config-manager --add-repo \
                https://download.docker.com/linux/centos/docker-ce.repo
            if [ -n "$DOCKER_VERSION" ]; then
                PKG="docker-ce-${DOCKER_VERSION}"
            else
                PKG="docker-ce"
            fi
            yum install -y ${PKG} docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
        *)
            error "不支持的操作系统: ${OS_ID}，请手动安装 Docker"
            exit 1
            ;;
    esac

    systemctl enable --now docker
    info "Docker 安装完成: $(docker --version)"
}

# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

if [ "$(id -u)" -ne 0 ]; then
    error "请使用 root 用户或 sudo 执行此脚本"
    exit 1
fi

# ── 1. 确保 Docker 可用 ─────────────────────────────────────
if ! command -v docker &>/dev/null; then
    warn "未检测到 Docker，自动安装..."
    install_docker
elif ! docker info &>/dev/null; then
    warn "Docker 守护进程未运行，启动中..."
    systemctl enable --now docker
else
    info "Docker 已就绪: $(docker --version)"
fi

# ── 2. 检测本机 IP ──────────────────────────────────────────
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$IP" ]; then
    IP="127.0.0.1"
    warn "无法检测本机 IP，使用 127.0.0.1"
fi

# ── 3. 构建镜像（不存在则构建）──────────────────────────────
if docker image inspect "${IMAGE_NAME}" &>/dev/null; then
    info "镜像 ${IMAGE_NAME} 已存在，跳过构建"
    info "如需重新构建: docker rmi ${IMAGE_NAME} && bash ${BUILD_SCRIPT}"
else
    info "镜像 ${IMAGE_NAME} 不存在，开始构建..."
    if [ -x "${BUILD_SCRIPT}" ]; then
        bash "${BUILD_SCRIPT}" "${IMAGE_NAME}"
    else
        error "构建脚本不存在: ${BUILD_SCRIPT}"
        exit 1
    fi
fi

# ── 4. 启动容器 ─────────────────────────────────────────────

# 幂等：同名容器已存在则先处理
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    EXISTING_STATUS=$(docker inspect -f '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null)
    if [ "$EXISTING_STATUS" = "running" ]; then
        info "容器 ${CONTAINER_NAME} 已在运行"
        echo ""
        echo "  ┌──────────────────────────────────────────┐"
        echo "  │  访问: http://${IP}:${FLASK_PORT}        │"
        echo "  │  日志: docker logs -f ${CONTAINER_NAME}  │"
        echo "  │  重启: docker restart ${CONTAINER_NAME}  │"
        echo "  │  停止: docker stop ${CONTAINER_NAME}     │"
        echo "  └──────────────────────────────────────────┘"
        echo ""
        exit 0
    fi
    info "容器 ${CONTAINER_NAME} 已停止，移除旧容器..."
    docker rm "${CONTAINER_NAME}" >/dev/null 2>&1
fi

info "启动容器..."

docker run -d \
    -p "${FLASK_PORT}:5000" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${SCRIPT_DIR}/toolkit:/app/toolkit" \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    "${IMAGE_NAME}"

# ── 5. 验证 ─────────────────────────────────────────────────
sleep 2

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    info "容器启动成功"
    echo ""
    echo "  ┌──────────────────────────────────────────┐"
    echo "  │  访问: http://${IP}:${FLASK_PORT}        │"
    echo "  │  日志: docker logs -f ${CONTAINER_NAME}  │"
    echo "  │  重启: docker restart ${CONTAINER_NAME}  │"
    echo "  │  停止: docker stop ${CONTAINER_NAME}     │"
    echo "  └──────────────────────────────────────────┘"
    echo ""
else
    error "容器启动失败，查看日志:"
    docker logs "${CONTAINER_NAME}" 2>&1 | tail -20
    exit 1
fi
