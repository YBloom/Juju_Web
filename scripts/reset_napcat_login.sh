#!/bin/bash
# scripts/reset_napcat_login.sh
# 作用: 停止 NapCat 容器，清理登录 Session (nt_qq)，然后重启
# 用法: sudo ./scripts/reset_napcat_login.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

CONTAINER_NAME="napcat_test"
# 修正后的配置路径 (Docker bind mount path)
CONFIG_ROOT="/opt/MusicalBot/config/napcat_test"

echo -e "${YELLOW}⚠️  正在重置 NapCat 登录状态...${NC}"

# 1. 停止容器
if sudo docker ps -a | grep -q "$CONTAINER_NAME"; then
    echo -e "Stopping container $CONTAINER_NAME..."
    sudo docker stop "$CONTAINER_NAME"
    sleep 2
fi

# 2. 清理配置文件
# 重点清理 nt_qq 开头的文件夹 (Session 数据)
if [ -d "$CONFIG_ROOT" ]; then
    echo -e "Cleaning session files in $CONFIG_ROOT..."
    
    # 清理 nt_qq 相关文件夹 (QQ 协议数据)
    sudo rm -rf "$CONFIG_ROOT"/nt_qq*
    
    # 清理可能存在的 token 文件
    sudo rm -f "$CONFIG_ROOT"/session.token
    
    # 注意：我们保留 config/ 目录，以免丢失监听端口配置。
    # 如果 config/ 是空的或不存在，NapCat 会根据环境变量重建。
    
    echo -e "${GREEN}Session cleared (nt_qq folders removed).${NC}"
else
    echo -e "${RED}Config dir not found: $CONFIG_ROOT${NC}"
    exit 1
fi

# 3. 重启容器
echo -e "Restarting container..."
sudo docker start "$CONTAINER_NAME"

echo -e "${GREEN}✅ 重置完成!${NC}"
echo -e "${YELLOW}!!! 重要提示 !!!${NC}"
echo -e "容器的环境变量 ACCOUNT 仍设置为旧账号 (3132859862)。"
echo -e "如果扫码新账号后仍然显示旧号，可能需要重建容器。"
echo -e "现在，请立即查看日志并扫码 (可能会先尝试快速登录失败，然后显示二维码):"
echo -e "${YELLOW}sudo docker logs -f --tail 100 $CONTAINER_NAME${NC}"
