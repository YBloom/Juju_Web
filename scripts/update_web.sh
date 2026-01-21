#!/bin/bash

# MusicalBot Web 异步更新脚本 (服务器端使用)
# 用法: sudo ./update_web.sh

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/opt/MusicalBot"

echo -e "${GREEN}=== MusicalBot Web 服务更新 ===${NC}"

# 1. 进入项目目录
cd $PROJECT_DIR || { echo -e "${RED}项目目录不存在${NC}"; exit 1; }

# 2. 拉取最新代码
echo -e "${YELLOW}拉取最新代码...${NC}"
sudo git pull || { echo -e "${RED}Git pull 失败${NC}"; exit 1; }

# 3. 检查依赖是否有变化
if sudo git diff HEAD@{1} HEAD -- requirements.txt | grep -q '^[+-]'; then
    echo -e "${YELLOW}检测到依赖变化，更新 Python 包...${NC}"
    .venv/bin/pip install -r requirements.txt
else
    echo "依赖无变化，跳过安装。"
fi

# 4. 重启 WebApp 服务
echo -e "${YELLOW}重启 WebApp...${NC}"
sudo supervisorctl restart musicalbot_web

# 5. 检查服务状态
echo -e "${YELLOW}服务状态:${NC}"
sudo supervisorctl status musicalbot_web

echo -e "${GREEN}更新完成！${NC}"
echo -e "查看日志: ${YELLOW}tail -f /var/log/musicalbot/web_out.log${NC}"
