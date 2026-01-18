"""测试盘票站 API 端点."""

import requests
import json
from datetime import datetime, timedelta

# 测试服务器地址
BASE_URL = "http://localhost:8000"


def test_marketplace_api():
    """测试盘票站 API."""
    
    print("🧪 开始测试盘票站 API...\n")
    
    # 1. 测试搜索端点（无需登录）
    print("1️⃣ 测试搜索端点...")
    response = requests.get(f"{BASE_URL}/api/marketplace/trades")
    print(f"   状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 成功获取 {data.get('count', 0)} 条交易")
    else:
        print(f"   ❌ 失败: {response.text}")
    
    # 2. 测试搜索（带筛选）
    print("\n2️⃣ 测试筛选搜索...")
    params = {"trade_type": "sell", "limit": 10}
    response = requests.get(f"{BASE_URL}/api/marketplace/trades", params=params)
    print(f"   状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 找到 {data.get('count', 0)} 条出票信息")
    else:
        print(f"   ❌ 失败: {response.text}")
    
    # 3. 测试创建交易（需要登录，预期失败）
    print("\n3️⃣ 测试创建交易（预期需要登录）...")
    trade_data = {
        "trade_type": "sell",
        "show_name": "测试剧目",
        "show_time": (datetime.now() + timedelta(days=7)).isoformat(),
        "price": 280.0,
        "quantity": 1,
        "description": "测试交易"
    }
    response = requests.post(
        f"{BASE_URL}/api/marketplace/trades",
        json=trade_data
    )
    print(f"   状态码: {response.status_code}")
    if response.status_code == 401:
        print("   ✅ 正确：需要登录才能创建交易")
    else:
        print(f"   ⚠️  预期外的响应: {response.text}")
    
    print("\n✨ API 测试完成！\n")


def test_subscription_api():
    """测试订阅 API."""
    
    print("🧪 开始测试订阅 API...\n")
    
    # 测试获取订阅列表（需要登录，预期失败）
    print("1️⃣ 测试获取订阅列表（预期需要登录）...")
    response = requests.get(f"{BASE_URL}/api/subscriptions")
    print(f"   状态码: {response.status_code}")
    if response.status_code == 401:
        print("   ✅ 正确：需要登录才能查看订阅")
    else:
        print(f"   ⚠️  预期外的响应: {response.text}")
    
    print("\n✨ 订阅 API 测试完成！\n")


if __name__ == "__main__":
    try:
        test_marketplace_api()
        test_subscription_api()
    except requests.exceptions.ConnectionError:
        print("❌ 错误：无法连接到服务器。请确保开发服务器正在运行（./dev.sh）")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
