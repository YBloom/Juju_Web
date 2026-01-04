#!/bin/bash

# 安全Git拉取脚本
# 用途: 在服务器上安全地拉取最新代码,处理可能的冲突

set -e

cd /opt/MusicalBot

echo "=========================================="
echo "  安全Git拉取"
echo "=========================================="
echo ""

# 1. 保存当前修改
echo "步骤 1: 保存当前修改..."
if [ -n "$(sudo git status --porcelain)" ]; then
    sudo git stash push -m "Auto-stash before pull $(date +%Y%m%d_%H%M%S)"
    echo "✓ 修改已保存"
    STASHED=true
else
    echo "✓ 无需保存"
    STASHED=false
fi

# 2. 拉取最新代码
echo ""
echo "步骤 2: 拉取最新代码..."
if sudo git pull origin v1; then
    echo "✓ 拉取成功"
else
    echo "✗ 拉取失败,请检查错误信息"
    exit 1
fi

# 3. 恢复之前的修改
if [ "$STASHED" = true ]; then
    echo ""
    echo "步骤 3: 恢复之前的修改..."
    if sudo git stash pop; then
        echo "✓ 修改已恢复"
    else
        echo "⚠ 恢复时有冲突,请手动解决"
        echo "冲突文件:"
        sudo git diff --name-only --diff-filter=U
        exit 1
    fi
fi

# 4. 重新应用服务器特定配置
echo ""
echo "步骤 4: 更新Umami配置..."
sudo sed -i 's|/umami/script.js|https://analytics.yaobii.com/script.js|' web/static/index.html
sudo sed -i 's/YOUR_WEBSITE_ID/65e0c212-9644-47e1-a5f4-9dc3b27cffd8/' web/static/index.html

# 5. 重启服务
echo ""
echo "步骤 5: 重启服务..."
sudo supervisorctl restart musicalbot_web

echo ""
echo "=========================================="
echo "✓ 完成!"
echo "=========================================="
echo ""
echo "当前状态:"
sudo git status --short
echo ""
