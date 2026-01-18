#!/bin/bash
# MusicalBot 部署脚本
# 功能: 提交本地代码 -> 推送到 GitHub -> 远程拉取 -> 重启 Bot

set -e  # 遇到错误立即停止

echo "🚀 [1/4] 提交本地代码..."
git add .
git commit -m "${1:-update: bot code changes}" || echo "⚠️  没有需要提交的更改"

echo "📤 [2/4] 推送到 GitHub..."
git push origin v1

echo "🔄 [3/4] 远程服务器拉取代码..."
ssh yyj "cd /opt/MusicalBot && sudo git pull origin v1"

echo "🔁 [4/4] 重启 Bot 服务..."
ssh yyj "sudo supervisorctl restart musical_qq_bot"

echo ""
echo "✅ 部署完成！"
echo "📋 查看日志: ssh yyj 'tail -f /var/log/musicalbot/bot_out.log'"
