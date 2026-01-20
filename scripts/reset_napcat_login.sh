#!/bin/bash
# scripts/reset_napcat_login.sh
# 作用: 停止 NapCat 容器，清理登录 Session，然后重启
# 用法: sudo ./scripts/reset_napcat_login.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

CONTAINER_NAME="napcat_test"
CONFIG_DIR="/opt/MusicalBot/config/napcat_test/config"

echo -e "${YELLOW}⚠️  正在重置 NapCat 登录状态...${NC}"

# 1. 停止容器
if sudo docker ps -a | grep -q "$CONTAINER_NAME"; then
    echo -e "Stopping container $CONTAINER_NAME..."
    sudo docker stop "$CONTAINER_NAME"
fi

# 2. 清理配置文件 (保留必要的，删除 Session)
if [ -d "$CONFIG_DIR" ]; then
    echo -e "Cleaning session files in $CONFIG_DIR..."
    # 删除 qq.json (登录凭证) 和其他相关文件，但保留基础配置如果需要
    # 通常删除 config 下的所有文件会让 NapCat 重新初始化
    sudo rm -rf "$CONFIG_DIR"/*
    echo -e "${GREEN}Session cleared.${NC}"
else
    echo -e "${RED}Config dir not found: $CONFIG_DIR${NC}"
fi

# 3. 重启容器 (它会自动生成新配置并请求扫码)
echo -e "Restarting container..."
sudo docker start "$CONTAINER_NAME"

echo -e "${GREEN}✅ 重置完成!${NC}"
echo -e "请立即运行以下命令查看二维码并扫码登录:"
echo -e "${YELLOW}sudo docker logs -f $CONTAINER_NAME${NC}"
