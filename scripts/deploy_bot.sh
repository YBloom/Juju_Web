#!/bin/bash

# Deploy QQ Bot Script
# Location: /opt/MusicalBot/scripts/deploy_bot.sh

SERVER_DIR="/opt/MusicalBot"
SERVICE_NAME="musical_qq_bot"

echo "=== Deploying $SERVICE_NAME ==="
cd $SERVER_DIR || exit 1

# 1. Git Pull
echo ">>> Pulling latest changes..."
git stash
git pull origin v1
git stash pop

# 2. Update Dependencies
echo ">>> Updating Python dependencies..."
/usr/bin/python3 -m pip install -r requirements.txt

# 3. Restart Supervisor Process
echo ">>> Restarting $SERVICE_NAME..."
sudo supervisorctl restart $SERVICE_NAME

# 4. Check Status
echo ">>> Checking status..."
sudo supervisorctl status $SERVICE_NAME

echo "=== Deployment Complete ==="
