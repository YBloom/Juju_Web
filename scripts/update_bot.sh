#!/bin/bash
# MusicalBot Bot 服务更新脚本
# 用法: sudo ./update_bot.sh
# 执行环境: AWS 服务器

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/opt/MusicalBot"
SERVICE_NAME="musical_qq_bot"

echo -e "${GREEN}=== MusicalBot Bot 服务更新 ===${NC}"

cd $PROJECT_DIR || { echo -e "${RED}项目目录不存在${NC}"; exit 1; }

echo -e "${YELLOW}[1/3] 拉取最新代码...${NC}"
sudo git pull origin v1 || { echo -e "${RED}Git pull 失败${NC}"; exit 1; }

echo -e "${YELLOW}[2/3] 检查依赖...${NC}"
if sudo git diff HEAD@{1} HEAD -- requirements.txt | grep -q '^[+-]'; then
    echo -e "${YELLOW}检测到依赖变化，更新 Python 包...${NC}"
    .venv/bin/pip install -r requirements.txt
else
    echo "依赖无变化，跳过安装。"
fi

echo -e "${YELLOW}[3/3] 重启 Bot 服务...${NC}"
sudo supervisorctl restart $SERVICE_NAME

echo -e "${GREEN}=== 更新完成 ===${NC}"
sudo supervisorctl status $SERVICE_NAME
echo -e "查看日志: ${YELLOW}tail -f /var/log/musicalbot/bot_out.log${NC}"
