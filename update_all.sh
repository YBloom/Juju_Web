#!/bin/bash

# MusicalBot 一键更新脚本 (服务器端使用)
# 用法: sudo ./scripts/update_all.sh

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/opt/MusicalBot"

echo -e "${GREEN}=== MusicalBot 全部服务更新 ===${NC}"

# 1. 进入项目目录
cd $PROJECT_DIR || { echo -e "${RED}项目目录不存在${NC}"; exit 1; }

# 2. 拉取最新代码
echo -e "${YELLOW}[1/4] 拉取最新代码...${NC}"
sudo git pull origin v1 || { echo -e "${RED}Git pull 失败${NC}"; exit 1; }

# 3. 检查依赖是否有变化
echo -e "${YELLOW}[2/4] 检查依赖...${NC}"
# 对比 HEAD 和上一次提交 (HEAD@{1}) 的 requirements.txt 差异
if sudo git diff HEAD@{1} HEAD -- requirements.txt | grep -q '^[+-]'; then
    echo -e "${YELLOW}检测到依赖变化，更新 Python 包...${NC}"
    .venv/bin/pip install -r requirements.txt
else
    echo "依赖无变化，跳过安装。"
fi

# 4. 重启服务
echo -e "${YELLOW}[3/4] 重启 WebApp 和 Bot...${NC}"
sudo supervisorctl restart musicalbot_web musical_qq_bot

# 5. 检查服务状态
echo -e "${YELLOW}[4/4] 服务状态:${NC}"
sudo supervisorctl status musicalbot_web musical_qq_bot

echo -e "${GREEN}=== 更新完成 ===${NC}"
echo -e "查看日志:"
echo -e "  Web: ${YELLOW}tail -f /var/log/musicalbot/web_out.log${NC}"
echo -e "  Bot: ${YELLOW}tail -f /var/log/musicalbot/bot_out.log${NC}"
