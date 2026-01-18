"""盘票站 API 使用示例演示."""

import requests
import json
from datetime import datetime, timedelta
from typing import Optional

BASE_URL = "http://localhost:8000"


class MarketplaceDemo:
    """盘票站 API 演示类."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.user_session_id: Optional[str] = None
    
    def print_section(self, title: str):
        """打印分隔线."""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    
    def print_result(self, response: requests.Response, show_body: bool = True):
        """打印请求结果."""
        print(f"📡 状态码: {response.status_code}")
        if show_body:
            try:
                data = response.json()
                print(f"📦 响应数据:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except:
                print(f"📦 响应: {response.text}")
        print()
    
    def demo_search_empty(self):
        """示例 1: 搜索交易（空数据库）."""
        self.print_section("示例 1: 搜索所有交易")
        
        print("🔍 GET /api/marketplace/trades")
        print("说明: 搜索所有交易信息，无需登录\n")
        
        response = self.session.get(f"{self.base_url}/api/marketplace/trades")
        self.print_result(response)
    
    def demo_search_with_filters(self):
        """示例 2: 带筛选条件的搜索."""
        self.print_section("示例 2: 筛选搜索")
        
        print("🔍 GET /api/marketplace/trades?trade_type=sell&limit=10")
        print("说明: 只搜索出票信息，限制返回 10 条\n")
        
        params = {
            "trade_type": "sell",
            "limit": 10
        }
        response = self.session.get(
            f"{self.base_url}/api/marketplace/trades",
            params=params
        )
        self.print_result(response)
    
    def demo_create_without_login(self):
        """示例 3: 未登录创建交易（失败）."""
        self.print_section("示例 3: 未登录创建交易")
        
        print("📝 POST /api/marketplace/trades")
        print("说明: 尝试创建交易但未登录，预期返回 401\n")
        
        trade_data = {
            "trade_type": "sell",
            "show_name": "三个女人的故事",
            "show_time": (datetime.now() + timedelta(days=7)).isoformat(),
            "price": 280.0,
            "original_price": 380.0,
            "quantity": 1,
            "seat_info": "一楼 3-5",
            "description": "票面380，280出，当天面交",
            "contact_info": "微信: demo123"
        }
        
        print("请求数据:")
        print(json.dumps(trade_data, indent=2, ensure_ascii=False))
        print()
        
        response = self.session.post(
            f"{self.base_url}/api/marketplace/trades",
            json=trade_data
        )
        self.print_result(response)
    
    def demo_search_by_show_name(self):
        """示例 4: 按剧目名称搜索."""
        self.print_section("示例 4: 按剧目名称搜索")
        
        print("🔍 GET /api/marketplace/trades?show_name=女巫")
        print("说明: 搜索包含'女巫'的交易\n")
        
        params = {"show_name": "女巫"}
        response = self.session.get(
            f"{self.base_url}/api/marketplace/trades",
            params=params
        )
        self.print_result(response)
    
    def demo_get_trade_detail(self):
        """示例 5: 获取交易详情."""
        self.print_section("示例 5: 获取交易详情")
        
        print("🔍 GET /api/marketplace/trades/1")
        print("说明: 获取 ID 为 1 的交易详情\n")
        
        response = self.session.get(f"{self.base_url}/api/marketplace/trades/1")
        self.print_result(response)
        
        print("💡 注意: contact_info 字段被隐藏，只显示 has_contact 布尔值")
        print("💡 如需查看联系方式，需要登录并使用 ?reveal_contact=true\n")
    
    def demo_api_structure(self):
        """示例 6: API 结构说明."""
        self.print_section("示例 6: 完整 API 端点列表")
        
        endpoints = [
            {
                "method": "GET",
                "path": "/api/marketplace/trades",
                "auth": "❌ 无需登录",
                "description": "搜索交易（支持筛选）",
                "params": "trade_type, status, show_name, user_id, limit, offset"
            },
            {
                "method": "POST",
                "path": "/api/marketplace/trades",
                "auth": "✅ 需要登录",
                "description": "创建新交易",
                "body": "trade_type, show_name, show_time, price, ..."
            },
            {
                "method": "GET",
                "path": "/api/marketplace/trades/{id}",
                "auth": "❌ 无需登录 (联系方式需登录)",
                "description": "获取交易详情",
                "params": "reveal_contact (可选)"
            },
            {
                "method": "PATCH",
                "path": "/api/marketplace/trades/{id}/status",
                "auth": "✅ 需要登录 (仅发布者)",
                "description": "更新交易状态",
                "body": "status"
            },
            {
                "method": "DELETE",
                "path": "/api/marketplace/trades/{id}",
                "auth": "✅ 需要登录 (仅发布者)",
                "description": "删除交易"
            },
            {
                "method": "GET",
                "path": "/api/marketplace/trades/my",
                "auth": "✅ 需要登录",
                "description": "获取我的交易"
            }
        ]
        
        for ep in endpoints:
            print(f"🔹 {ep['method']:6} {ep['path']}")
            print(f"   权限: {ep['auth']}")
            print(f"   功能: {ep['description']}")
            if 'params' in ep:
                print(f"   参数: {ep['params']}")
            if 'body' in ep:
                print(f"   请求体: {ep['body']}")
            print()
    
    def demo_data_model(self):
        """示例 7: 数据模型说明."""
        self.print_section("示例 7: 数据模型结构")
        
        print("📊 TicketTrade 模型字段:\n")
        
        fields = [
            ("id", "int", "交易 ID (自动生成)"),
            ("user_id", "str", "发布者用户 ID"),
            ("type", "TradeType", "交易类型: sell/buy/exchange"),
            ("status", "TradeStatus", "状态: open/locked/completed/cancelled"),
            ("show_name", "str", "剧目名称"),
            ("show_time", "datetime", "演出时间"),
            ("price", "float", "交易价格"),
            ("original_price", "float?", "票面原价 (可选)"),
            ("quantity", "int", "数量 (默认 1)"),
            ("seat_info", "str?", "座位信息 (可选)"),
            ("description", "str", "描述信息"),
            ("contact_info", "str?", "联系方式 (隐藏字段)"),
            ("play_id", "int?", "关联剧目 ID (可选)"),
            ("created_at", "datetime", "创建时间"),
            ("updated_at", "datetime", "更新时间"),
        ]
        
        for name, type_, desc in fields:
            print(f"  • {name:20} {type_:15} - {desc}")
        
        print("\n📝 枚举类型:\n")
        print("  TradeType:")
        print("    • sell     - 出票")
        print("    • buy      - 求票")
        print("    • exchange - 换票")
        print()
        print("  TradeStatus:")
        print("    • open      - 开启 (可交易)")
        print("    • locked    - 锁定 (正在沟通)")
        print("    • completed - 完成")
        print("    • cancelled - 取消")
        print()
    
    def demo_use_cases(self):
        """示例 8: 实际使用场景."""
        self.print_section("示例 8: 实际使用场景")
        
        scenarios = [
            {
                "title": "场景 1: 用户发布出票信息",
                "steps": [
                    "1. 用户通过 QQ Bot 或 Web 登录",
                    "2. POST /api/marketplace/trades",
                    "3. 提供剧目、时间、价格、座位等信息",
                    "4. 系统创建交易记录，返回 trade_id"
                ]
            },
            {
                "title": "场景 2: 其他用户浏览盘票信息",
                "steps": [
                    "1. 无需登录，访问 GET /api/marketplace/trades",
                    "2. 可筛选类型（出/求/换）、剧目名称",
                    "3. 查看交易列表，contact_info 被隐藏",
                    "4. 点击感兴趣的交易查看详情"
                ]
            },
            {
                "title": "场景 3: 用户查看联系方式",
                "steps": [
                    "1. 用户登录后，访问交易详情",
                    "2. GET /api/marketplace/trades/123?reveal_contact=true",
                    "3. 系统验证登录状态，返回完整联系方式",
                    "4. 用户通过微信/QQ 联系发布者"
                ]
            },
            {
                "title": "场景 4: 发布者管理自己的交易",
                "steps": [
                    "1. 用户登录后，访问 GET /api/marketplace/trades/my",
                    "2. 查看自己发布的所有交易",
                    "3. 票已出，更新状态为 completed",
                    "4. PATCH /api/marketplace/trades/123/status",
                    "5. 或直接删除: DELETE /api/marketplace/trades/123"
                ]
            }
        ]
        
        for scenario in scenarios:
            print(f"🎬 {scenario['title']}\n")
            for step in scenario['steps']:
                print(f"   {step}")
            print()
    
    def run_all_demos(self):
        """运行所有演示."""
        print("\n" + "🎭" * 30)
        print("  盘票站 API 使用示例演示")
        print("🎭" * 30)
        
        # 实际 API 调用示例
        self.demo_search_empty()
        self.demo_search_with_filters()
        self.demo_create_without_login()
        self.demo_search_by_show_name()
        
        # 文档说明
        self.demo_api_structure()
        self.demo_data_model()
        self.demo_use_cases()
        
        print("\n" + "✨" * 30)
        print("  演示完成！")
        print("✨" * 30 + "\n")


if __name__ == "__main__":
    demo = MarketplaceDemo()
    
    try:
        demo.run_all_demos()
    except requests.exceptions.ConnectionError:
        print("\n❌ 错误：无法连接到服务器")
        print("💡 请确保开发服务器正在运行：./dev.sh\n")
    except Exception as e:
        print(f"\n❌ 演示失败: {e}\n")
        import traceback
        traceback.print_exc()
