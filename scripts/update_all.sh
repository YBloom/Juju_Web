#!/bin/bash

# MusicalBot 一键更新脚本 (服务器端使用)
# 用法: sudo ./update.sh

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/opt/MusicalBot"

echo -e "${GREEN}=== MusicalBot 全部服务更新 ===${NC}"

# ... (cd and pull logic) ...

# 4. 重启服务
echo -e "${YELLOW}重启 WebApp 和 Bot...${NC}"
sudo supervisorctl restart musicalbot_web musical_qq_bot

# 5. 检查服务状态
echo -e "${YELLOW}服务状态:${NC}"
sudo supervisorctl status musicalbot_web musical_qq_bot

echo -e "${GREEN}更新完成！${NC}"

