#!/bin/bash
# 启动 Web 服务 (作为后台/独立服务)
# 使用方法: ./scripts/start_web.sh

echo "🚀 Starting Web Service..."
source .venv/bin/activate
export HLQ_ENABLE_CRAWLER=True
export MAINTENANCE_MODE=0

# uvicorn config can be adjusted here (workers, port, etc.)
exec uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload
