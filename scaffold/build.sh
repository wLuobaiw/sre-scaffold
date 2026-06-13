#!/bin/bash
set -e

IMAGE_NAME="${1:-sre-scaffold:1.0}"

cd "$(dirname "$0")"

echo "[INFO] Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" -f Dockerfile .

echo "[INFO] Build complete: ${IMAGE_NAME}"
