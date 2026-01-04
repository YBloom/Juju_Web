#!/bin/bash

# MusicalBot Lightsail Deployment Script
# 适用于 Ubuntu 24.04 LTS (推荐)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== 开始 MusicalBot 部署 ===${NC}"

# 1. 检查 Root 权限
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}请使用 sudo 运行此脚本: sudo ./scripts/deploy_lightsail.sh${NC}"
  exit 1
fi

# 2. 基础路径设置
PROJECT_DIR="/opt/MusicalBot"
CURRENT_DIR=$(pwd)
USER="ubuntu"  # Lightsail 默认用户

echo -e "${YELLOW}更新系统软件包...${NC}"
apt-get update && apt-get upgrade -y

echo -e "${YELLOW}安装依赖库...${NC}"
# 安装 Python 3.12, venv, Supervisor, Nginx, Certbot, Docker (可选)
apt-get install -y python3.12 python3.12-venv python3-pip git unzip supervisor nginx curl acl python3-certbot-nginx

# 3. 设置虚拟内存 (Swap) - 即使是 4GB，建议也加上 2GB Swap 以防万一
echo -e "${YELLOW}设置 2GB 虚拟内存 (Swap)...${NC}"
if [ ! -f "/swapfile" ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Swap 设置完成。"
else
    echo "Swap 已存在，跳过。"
fi

# 4. 设置项目目录
echo -e "${YELLOW}配置项目目录: ${PROJECT_DIR}${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    # 如果目标目录不存在，假设当前目录就是代码源，复制过去
    echo "创建并复制文件到 ${PROJECT_DIR}..."
    mkdir -p $PROJECT_DIR
    cp -r . $PROJECT_DIR
    # Ensure .env is copied if present
    if [ -f ".env" ]; then
        cp .env $PROJECT_DIR/
        echo "已同步 .env 配置"
    fi
else
    echo "目录已存在，执行同步..."
    rsync -av --exclude '.venv' --exclude '__pycache__' --exclude '.git' . $PROJECT_DIR/
    if [ -f ".env" ]; then
        cp .env $PROJECT_DIR/
        echo "已同步 .env 配置"
    fi
fi

# 修复权限
chown -R $USER:$USER $PROJECT_DIR
# 给予当前用户对 log 目录的写权限
mkdir -p /var/log/musicalbot
chown -R $USER:$USER /var/log/musicalbot

# 4. Python 环境设置
echo -e "${YELLOW}设置 Python 虚拟环境...${NC}"
cd $PROJECT_DIR
if [ ! -d ".venv" ]; then
    sudo -u $USER python3.12 -m venv .venv
fi

echo "安装 Python 依赖..."
sudo -u $USER .venv/bin/pip install --upgrade pip
sudo -u $USER .venv/bin/pip install -r requirements.txt

# 5. 配置 Supervisor
echo -e "${YELLOW}配置 Supervisor...${NC}"
cp config/supervisor_deploy.conf /etc/supervisor/conf.d/musicalbot.conf
supervisorctl reread
supervisorctl update

# 6. 配置 Nginx
echo -e "${YELLOW}配置 Nginx...${NC}"
cp config/nginx_deploy.conf /etc/nginx/sites-available/musicalbot
ln -sf /etc/nginx/sites-available/musicalbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo -e "${GREEN}=== 基础服务部署完成 ===${NC}"
echo -e "${YELLOW}设置 SSL 证书 (HTTPS):${NC}"
echo "请确保域名 yyj.yaobii.com 已解析到此服务器 IP 后运行:"
echo "  sudo certbot --nginx -d yyj.yaobii.com"
echo ""
echo -e "${YELLOW}关于 NapCat / QQ 机器人:${NC}"
echo "当前部署为 Phase 1 (仅 WebApp)，机器人进程已在 Supervisor 中禁用。"
echo "若未来需要启动机器人，请编辑 /etc/supervisor/conf.d/musicalbot.conf 取消注释对应部分。"

echo -e "${GREEN}Web 服务应已通过 Nginx 启动。${NC}"
echo -e "访问地址: http://yyj.yaobii.com"
echo -e "日志查看: tail -f /var/log/musicalbot/*.log"

