#!/bin/bash
# 云端Saoju数据快速同步脚本
# 用法: ./scripts/sync_saoju_to_cloud.sh <服务器IP>

set -e

if [ -z "$1" ]; then
    echo "❌ 错误: 请提供服务器IP地址"
    echo "用法: $0 <服务器IP>"
    echo "示例: $0 54.123.45.67"
    exit 1
fi

SERVER_IP=$1
SERVER_USER="ubuntu"
REMOTE_DIR="~/MusicalBot"

echo "🚀 开始同步Saoju数据到云端..."
echo "服务器: $SERVER_IP"
echo ""

# 1. 检查本地缓存文件
if [ ! -f "data/saoju_service_cache.json" ]; then
    echo "❌ 本地缓存文件不存在: data/saoju_service_cache.json"
    exit 1
fi

LOCAL_SIZE=$(du -h data/saoju_service_cache.json | cut -f1)
echo "✓ 本地缓存文件: $LOCAL_SIZE"

# 2. 上传缓存文件
echo ""
echo "📤 上传缓存文件到云端..."
scp data/saoju_service_cache.json ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/data/ || {
    echo "❌ 上传失败"
    exit 1
}
echo "✓ 上传成功"

# 3. 验证云端文件
echo ""
echo "🔍 验证云端数据..."
ssh ${SERVER_USER}@${SERVER_IP} "cd ${REMOTE_DIR} && python3.12 -c \"
import json
with open('data/saoju_service_cache.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    artists = data.get('artists_map', {})
    print(f'✓ 艺术家数量: {len(artists)}')
    
    # 测试关键演员
    test_names = ['陈玉婷', '丁辰西', '阿云嘎', '郑云龙']
    missing = [n for n in test_names if n not in artists]
    if missing:
        print(f'⚠️  缺失演员: {missing}')
    else:
        print('✓ 关键演员全部存在')
\"" || {
    echo "❌ 验证失败"
    exit 1
}

# 4. 重启服务
echo ""
echo "🔄 重启MusicalBot服务..."
ssh ${SERVER_USER}@${SERVER_IP} "sudo systemctl restart musicalbot" || {
    echo "⚠️  重启失败（可能需要手动重启）"
}

# 5. 显示服务状态
echo ""
echo "📊 服务状态:"
ssh ${SERVER_USER}@${SERVER_IP} "sudo systemctl status musicalbot --no-pager -l | head -15"

echo ""
echo "✅ 同步完成！"
echo ""
echo "请访问云端网站测试CoСast查询功能："
echo "   https://<你的域名>/cocast"
echo ""
echo "测试演员: 丁辰西, 陈玉婷"
