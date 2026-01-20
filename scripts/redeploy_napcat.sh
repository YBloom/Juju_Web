#!/bin/bash
# scripts/redeploy_napcat.sh
# 作用: 销毁并重建 NapCat 容器，确保环境变量(ACCOUNT)更新且端口(3001)正确映射
# 用法: sudo ./scripts/redeploy_napcat.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

CONTAINER_NAME="napcat_test"
IMAGE_NAME="mlikiowa/napcat-docker:latest"
CONFIG_ROOT="/opt/MusicalBot/config/napcat_test"

# 新的 QQ 号
NEW_ACCOUNT="3044829389"

echo -e "${YELLOW}⚠️  正在重新部署 NapCat 容器...${NC}"

# 1. 停止并删除旧容器
if sudo docker ps -a | grep -q "$CONTAINER_NAME"; then
    echo -e "Removing old container $CONTAINER_NAME..."
    sudo docker rm -f "$CONTAINER_NAME"
fi

# 2. 确保配置目录存在 (保留之前的 session 清理结果，如果不放心可以再次清理)
mkdir -p "$CONFIG_ROOT"

# 3. 启动新容器
# -p 3001:3001 : 映射 WebSocket 端口
# -e ACCOUNT=... : 设置默认账号
# -v ... : 挂载配置目录
echo -e "Starting new container with ACCOUNT=$NEW_ACCOUNT and Port 3001..."

sudo docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p 3001:3001 \
    -p 6099:6099 \
    -e ACCOUNT=$NEW_ACCOUNT \
    -e WS_ENABLE=true \
    -e HTTP_ENABLE=true \
    -v "$CONFIG_ROOT":/app/.config/QQ \
    "$IMAGE_NAME"

echo -e "${GREEN}✅ 部署完成!${NC}"
echo -e "请立即运行以下命令查看二维码并扫码登录:"
echo -e "${YELLOW}sudo docker logs -f $CONTAINER_NAME${NC}"
