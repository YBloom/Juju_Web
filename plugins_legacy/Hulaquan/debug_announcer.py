"""
呼啦圈上新通知调试工具

使用说明：
1. 模拟上新数据测试
2. 测试用户关注模式
3. 测试消息生成逻辑
4. 查看定时任务状态
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any


class AnnouncerDebugger:
    """上新通知调试器"""
    
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.mock_data = {}
        
    def create_mock_ticket(self, ticket_id: str, event_id: str, 
                          categorized: str = "new", 
                          title: str = "测试剧目",
                          date: str = "2025-10-20",
                          seat: str = "A区1排1座",
                          price: str = "100") -> Dict:
        """创建模拟票务数据"""
        return {
            "id": ticket_id,
            "event_id": event_id,
            "categorized": categorized,  # new, add, pending, return, back, sold
            "message": f"[{ticket_id}] {title} | {date} | {seat} | ¥{price}",
            "title": title,
            "date": date,
            "seat": seat,
            "price": price
        }
    
    def create_mock_result(self, tickets: List[Dict]) -> Dict:
        """创建模拟的 compare_to_database_async 返回结果"""
        categorized = {
            "new": [],
            "add": [],
            "pending": [],
            "return": [],
            "back": [],
            "sold": []
        }
        
        event_id_to_ticket_ids = {}
        event_msgs = {}
        tickets_dict = {}
        
        for ticket in tickets:
            tid = ticket["id"]
            eid = ticket["event_id"]
            cat = ticket["categorized"]
            
            # 归类
            categorized[cat].append(tid)
            
            # event到ticket的映射
            if eid not in event_id_to_ticket_ids:
                event_id_to_ticket_ids[eid] = []
            event_id_to_ticket_ids[eid].append(tid)
            
            # event信息
            if eid not in event_msgs:
                event_msgs[eid] = f"【{ticket['title']}】"
            
            # ticket详情
            tickets_dict[tid] = ticket
        
        prefixes = {
            "new": "🆕上新",
            "add": "➕补票",
            "pending": "⏰待开",
            "return": "🔄回流",
            "back": "📈增票",
            "sold": "📉减票"
        }
        
        return {
            "events": event_id_to_ticket_ids,
            "events_prefixes": event_msgs,
            "prefix": prefixes,
            "categorized": categorized,
            "tickets": tickets_dict
        }
    
    def print_user_settings(self, user_id: str):
        """打印用户的关注设置"""
        from plugins.Hulaquan.data_managers import User
        
        user = User.get_user(user_id)
        if not user:
            print(f"❌ 用户 {user_id} 不存在")
            return
        
        print(f"\n{'='*60}")
        print(f"👤 用户 {user_id} 的关注设置：")
        print(f"{'='*60}")
        
        # 全局模式
        all_mode = user.get("attention_to_hulaquan", 0)
        mode_desc = {
            0: "❌ 不接受通知",
            1: "🆕 只推送上新/补票",
            2: "🆕🔄 上新/补票/回流",
            3: "🆕🔄📊 上新/补票/回流/增减票"
        }
        print(f"全局模式: {mode_desc.get(int(all_mode), '未知')}")
        
        # 关注的剧目
        events = User.subscribe_events(user_id)
        if events:
            print(f"\n📋 关注的剧目 ({len(events)}个):")
            for event in events:
                print(f"  - EventID: {event['id']}, 模式: {event.get('mode', 'N/A')}")
        else:
            print("\n📋 关注的剧目: 无")
        
        # 关注的场次
        tickets = User.subscribe_tickets(user_id)
        if tickets:
            print(f"\n🎫 关注的场次 ({len(tickets)}个):")
            for ticket in tickets:
                print(f"  - TicketID: {ticket['id']}, 模式: {ticket.get('mode', 'N/A')}")
        else:
            print("\n🎫 关注的场次: 无")
        
        print(f"{'='*60}\n")
    
    def test_generate_announce_text(self, mock_result: Dict, user_id: str):
        """测试消息生成逻辑"""
        from plugins.Hulaquan.data_managers import User
        
        MODE = {
            "add": 1,
            "new": 1,
            "pending": 1,
            "return": 2,
            "back": 3,
            "sold": 3,
        }
        
        user = User.get_user(user_id)
        if not user:
            print(f"❌ 用户 {user_id} 不存在")
            return []
        
        messages = self.plugin._Hulaquan__generate_announce_text(
            MODE,
            mock_result["events"],
            mock_result["events_prefixes"],
            mock_result["prefix"],
            mock_result["categorized"],
            mock_result["tickets"],
            user_id,
            user,
            is_group=False
        )
        
        print(f"\n{'='*60}")
        print(f"📨 为用户 {user_id} 生成的消息：")
        print(f"{'='*60}")
        
        if not messages:
            print("⚠️  没有生成任何消息！")
            print("\n可能的原因：")
            print("1. 用户的全局模式为0（不接受通知）")
            print("2. 用户没有关注相关剧目/场次")
            print("3. 票务变动类型不在用户关注范围内")
        else:
            for idx, msg_group in enumerate(messages, 1):
                print(f"\n消息组 #{idx}:")
                for msg in msg_group:
                    print(f"  {msg}")
        
        print(f"{'='*60}\n")
        return messages
    
    def check_task_status(self):
        """检查定时任务状态"""
        print(f"\n{'='*60}")
        print("⏰ 定时任务状态检查：")
        print(f"{'='*60}")
        
        print(f"定时任务运行状态: {'✅ 运行中' if self.plugin._hulaquan_announcer_running else '❌ 已停止'}")
        print(f"检测间隔: {self.plugin._hulaquan_announcer_interval} 秒")
        
        if self.plugin._hulaquan_announcer_task:
            print(f"任务对象: {self.plugin._hulaquan_announcer_task}")
            print(f"任务完成: {'是' if self.plugin._hulaquan_announcer_task.done() else '否'}")
        else:
            print("任务对象: None")
        
        print(f"{'='*60}\n")
    
    async def simulate_announcer_once(self, mock_result: Dict = None, 
                                     user_id: str = None,
                                     announce_admin_only: bool = True):
        """模拟执行一次上新检测（不实际发送消息）"""
        print(f"\n{'='*60}")
        print("🧪 模拟上新检测执行：")
        print(f"{'='*60}")
        
        if mock_result is None:
            print("❌ 未提供模拟数据，无法执行")
            return
        
        MODE = {
            "add": 1,
            "new": 1,
            "pending": 1,
            "return": 2,
            "back": 3,
            "sold": 3,
        }
        
        from plugins.Hulaquan.data_managers import User
        
        if announce_admin_only:
            _users = {User.admin_id: User.get_user(User.admin_id)}
        elif user_id:
            _users = {user_id: User.get_user(user_id)}
        else:
            _users = User.users()
        
        print(f"\n将为 {len(_users)} 个用户生成通知：")
        
        for uid, user in _users.items():
            if not user:
                print(f"  ⚠️  用户 {uid} 不存在，跳过")
                continue
            
            messages = self.plugin._Hulaquan__generate_announce_text(
                MODE,
                mock_result["events"],
                mock_result["events_prefixes"],
                mock_result["prefix"],
                mock_result["categorized"],
                mock_result["tickets"],
                uid,
                user,
                is_group=False
            )
            
            if messages:
                print(f"\n  ✅ 用户 {uid}: 生成 {len(messages)} 组消息")
                for idx, msg_group in enumerate(messages, 1):
                    full_msg = "\n\n".join(msg_group)
                    print(f"    消息 #{idx} 长度: {len(full_msg)} 字符")
                    print(f"    预览: {full_msg[:100]}...")
            else:
                print(f"  ⚠️  用户 {uid}: 没有生成消息")
        
        print(f"\n{'='*60}\n")


# 使用示例函数
async def run_debug_tests(plugin):
    """运行调试测试"""
    debugger = AnnouncerDebugger(plugin)
    
    print("\n" + "="*80)
    print("🔍 呼啦圈上新通知调试工具")
    print("="*80)
    
    # 1. 检查定时任务状态
    debugger.check_task_status()
    
    # 2. 获取一个测试用户ID（使用管理员ID或提供具体ID）
    from plugins.Hulaquan.data_managers import User
    test_user_id = User.admin_id
    
    # 3. 打印用户设置
    debugger.print_user_settings(test_user_id)
    
    # 4. 创建模拟数据
    print("📦 创建模拟上新数据...")
    mock_tickets = [
        # 上新票
        debugger.create_mock_ticket("10001", "1001", "new", "测试剧目A", "2025-10-20", "A区1排1座", "100"),
        debugger.create_mock_ticket("10002", "1001", "new", "测试剧目A", "2025-10-21", "A区1排2座", "100"),
        # 补票
        debugger.create_mock_ticket("10003", "1002", "add", "测试剧目B", "2025-10-22", "B区2排1座", "150"),
        # 回流票
        debugger.create_mock_ticket("10004", "1003", "return", "测试剧目C", "2025-10-23", "C区3排1座", "200"),
    ]
    
    mock_result = debugger.create_mock_result(mock_tickets)
    print(f"✅ 创建了 {len(mock_tickets)} 张模拟票")
    print(f"   - 上新: {len(mock_result['categorized']['new'])} 张")
    print(f"   - 补票: {len(mock_result['categorized']['add'])} 张")
    print(f"   - 回流: {len(mock_result['categorized']['return'])} 张")
    
    # 5. 测试消息生成
    messages = debugger.test_generate_announce_text(mock_result, test_user_id)
    
    # 6. 模拟完整执行流程
    await debugger.simulate_announcer_once(mock_result, test_user_id)
    
    print("\n" + "="*80)
    print("✅ 调试测试完成！")
    print("="*80)


# 快捷调试命令示例
def print_usage():
    """打印使用说明"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║           呼啦圈上新通知调试工具 - 使用说明                      ║
╚════════════════════════════════════════════════════════════════╝

在 Python REPL 或脚本中使用：

from plugins.Hulaquan.debug_announcer import AnnouncerDebugger, run_debug_tests

# 方法1: 运行完整调试测试
await run_debug_tests(plugin_instance)

# 方法2: 单独使用调试器
debugger = AnnouncerDebugger(plugin_instance)

# 检查任务状态
debugger.check_task_status()

# 查看用户设置
debugger.print_user_settings("用户ID")

# 创建模拟数据并测试
mock_tickets = [
    debugger.create_mock_ticket("10001", "1001", "new", "剧目名", "2025-10-20", "A区", "100"),
]
mock_result = debugger.create_mock_result(mock_tickets)
messages = debugger.test_generate_announce_text(mock_result, "用户ID")

# 模拟完整执行
await debugger.simulate_announcer_once(mock_result, user_id="用户ID")

╔════════════════════════════════════════════════════════════════╗
║                     票务状态类型说明                             ║
╚════════════════════════════════════════════════════════════════╝

- "new"     : 🆕 上新 (模式1+可见)
- "add"     : ➕ 补票 (模式1+可见)
- "pending" : ⏰ 待开票 (模式1+可见)
- "return"  : 🔄 回流 (模式2+可见)
- "back"    : 📈 增票 (模式3+可见)
- "sold"    : 📉 减票 (模式3+可见)

╔════════════════════════════════════════════════════════════════╗
║                     用户关注模式                                ║
╚════════════════════════════════════════════════════════════════╝

模式0: 不接受任何通知
模式1: 只推送 上新/补票/待开票
模式2: 推送 上新/补票/待开票 + 回流
模式3: 推送 上新/补票/待开票 + 回流 + 增减票

""")


if __name__ == "__main__":
    print_usage()
