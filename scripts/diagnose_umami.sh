#!/bin/bash

# Umami 快速诊断脚本
# 用途: 自动诊断 Umami 部署问题

echo "=========================================="
echo "  Umami 诊断工具"
echo "=========================================="
echo ""

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /opt/MusicalBot

echo "1️⃣ 检查 Docker 容器状态..."
echo "----------------------------------------"
sudo docker-compose -f docker-compose.umami.yml ps
echo ""

echo "2️⃣ 检查容器日志(最近 20 行)..."
echo "----------------------------------------"
sudo docker-compose -f docker-compose.umami.yml logs --tail=20
echo ""

echo "3️⃣ 检查端口占用..."
echo "----------------------------------------"
sudo netstat -tulnp | grep 3000
echo ""

echo "4️⃣ 检查 Nginx 配置..."
echo "----------------------------------------"
sudo nginx -t
echo ""

echo "5️⃣ 检查 Nginx 是否包含 Umami 配置..."
echo "----------------------------------------"
if sudo grep -q "umami" /etc/nginx/sites-available/musicalbot; then
    echo -e "${GREEN}✓ Nginx 配置包含 Umami 代理${NC}"
    sudo grep -A 5 "location /umami" /etc/nginx/sites-available/musicalbot
else
    echo -e "${RED}✗ Nginx 配置缺少 Umami 代理规则${NC}"
fi
echo ""

echo "6️⃣ 测试本地连接..."
echo "----------------------------------------"
curl -I http://localhost:3000 2>&1 | head -5
echo ""

echo "=========================================="
echo "  诊断完成"
echo "=========================================="
echo ""
echo "📝 常见问题修复:"
echo ""
echo "如果容器未运行:"
echo "  sudo docker-compose -f docker-compose.umami.yml up -d"
echo ""
echo "如果 Nginx 配置缺失:"
echo "  需要手动添加 Umami 代理规则到 /etc/nginx/sites-available/musicalbot"
echo ""
echo "如果端口冲突:"
echo "  检查是否有其他服务占用 3000 端口"
echo ""
