"""测试结构化盘票站 API V2."""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"


def test_api_v2():
    """测试 V2 API."""
    
    print("🧪 开始测试结构化盘票站 API V2...\n")
    
    # 1. 测试搜索挂单
    print("1️⃣ 测试搜索挂单...")
    response = requests.get(f"{BASE_URL}/api/marketplace/listings")
    print(f"   状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 成功获取 {data.get('count', 0)} 个挂单")
    else:
        print(f"   ❌ 失败: {response.text}")
    
    # 2. 测试搜索细项
    print("\n2️⃣ 测试搜索细项...")
    response = requests.get(f"{BASE_URL}/api/marketplace/items")
    print(f"   状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 成功获取 {data.get('count', 0)} 个细项")
    else:
        print(f"   ❌ 失败: {response.text}")
    
    # 3. 测试筛选搜索（持有的票）
    print("\n3️⃣ 测试筛选搜索 (HAVE)...")
    params = {"direction": "have", "limit": 10}
    response = requests.get(f"{BASE_URL}/api/marketplace/items", params=params)
    print(f"   状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 找到 {data.get('count', 0)} 条持有的票")
    else:
        print(f"   ❌ 失败: {response.text}")
    
    # 4. 测试创建挂单（预期需要登录）
    print("\n4️⃣ 测试创建挂单（预期需要登录）...")
    listing_data = {
        "items": [
            {
                "direction": "have",
                "show_name": "测试剧目",
                "show_time": (datetime.now() + timedelta(days=7)).isoformat(),
                "price": 280.0,
                "seat_info": "一楼 3-5"
            }
        ],
        "description": "测试挂单",
        "requirements": "测试要求"
    }
    response = requests.post(
        f"{BASE_URL}/api/marketplace/listings",
        json=listing_data
    )
    print(f"   状态码: {response.status_code}")
    if response.status_code == 401:
        print("   ✅ 正确：需要登录才能创建挂单")
    else:
        print(f"   ⚠️  预期外的响应: {response.text}")
    
    # 5. 测试智能匹配
    print("\n5️⃣ 测试智能匹配...")
    params = {"show_name": "女巫", "direction": "have"}
    response = requests.get(f"{BASE_URL}/api/marketplace/match", params=params)
    print(f"   状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ 找到 {data.get('count', 0)} 个匹配项")
    else:
        print(f"   ❌ 失败: {response.text}")
    
    print("\n✨ API V2 测试完成！\n")
    
    # 6. API 端点总结
    print("="*60)
    print("📋 V2 API 端点列表:\n")
    endpoints = [
        ("GET", "/api/marketplace/listings", "搜索挂单"),
        ("POST", "/api/marketplace/listings", "创建挂单 (需登录)"),
        ("GET", "/api/marketplace/listings/{id}", "获取挂单详情"),
        ("PATCH", "/api/marketplace/listings/{id}/status", "更新状态 (需登录)"),
        ("DELETE", "/api/marketplace/listings/{id}", "删除挂单 (需登录)"),
        ("GET", "/api/marketplace/items", "搜索细项 (结构化匹配)"),
        ("GET", "/api/marketplace/match", "智能匹配"),
        ("GET", "/api/marketplace/listings/my", "我的挂单 (需登录)"),
    ]
    
    for method, path, desc in endpoints:
        print(f"   {method:6} {path:45} {desc}")
    print()


if __name__ == "__main__":
    try:
        test_api_v2()
    except requests.exceptions.ConnectionError:
        print("❌ 错误：无法连接到服务器。请确保开发服务器正在运行（./dev.sh）")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
