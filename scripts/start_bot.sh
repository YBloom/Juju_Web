#!/bin/bash
# 启动 Bot 服务 (负责通知推送)
# 使用方法: ./scripts/start_bot.sh

echo "🤖 Starting Bot Service..."
source .venv/bin/activate

# Ensure configuration exists (add checks if needed)
if [ ! -d "config" ]; then
    echo "⚠️  Warning: 'config' directory not found. Bot might fail to start."
fi

exec python3 main_bot_v2.py
