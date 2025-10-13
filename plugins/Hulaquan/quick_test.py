"""
快速测试脚本 - 呼啦圈上新通知功能

这个脚本可以独立运行，用于快速测试通知功能的各个环节
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def quick_test():
    """快速测试函数"""
    print("="*80)
    print("🚀 呼啦圈上新通知快速测试")
    print("="*80)
    
    try:
        # 导入必要的模块
        from plugins.Hulaquan.data_managers import User, Hlq
        from plugins.Hulaquan.debug_announcer import AnnouncerDebugger
        
        print("\n✅ 模块导入成功")
        
        # 测试1: 检查用户数据
        print("\n" + "="*80)
        print("📊 测试1: 用户数据检查")
        print("="*80)
        
        users = User.users()
        print(f"总用户数: {len(users)}")
        
        if users:
            # 选择第一个用户进行测试
            test_user_id = list(users.keys())[0]
            print(f"\n测试用户ID: {test_user_id}")
            
            user_info = users[test_user_id]
            attention_mode = user_info.get("attention_to_hulaquan", 0)
            print(f"关注模式: {attention_mode}")
            
            mode_desc = {
                0: "❌ 不接受通知",
                1: "✅ 上新/补票",
                2: "✅ 上新/补票/回流",
                3: "✅ 上新/补票/回流/增减票"
            }
            print(f"模式说明: {mode_desc.get(int(attention_mode), '未知')}")
            
            # 检查关注的剧目
            events = User.subscribe_events(test_user_id)
            print(f"\n关注的剧目数: {len(events) if events else 0}")
            if events and len(events) > 0:
                print("示例:")
                for e in events[:3]:
                    print(f"  - EventID: {e['id']}, 模式: {e.get('mode', 'N/A')}")
            
            # 检查关注的场次
            tickets = User.subscribe_tickets(test_user_id)
            print(f"\n关注的场次数: {len(tickets) if tickets else 0}")
            if tickets and len(tickets) > 0:
                print("示例:")
                for t in tickets[:3]:
                    print(f"  - TicketID: {t['id']}, 模式: {t.get('mode', 'N/A')}")
        else:
            print("⚠️  没有用户数据")
            test_user_id = None
        
        # 测试2: 检查呼啦圈数据
        print("\n" + "="*80)
        print("📊 测试2: 呼啦圈数据检查")
        print("="*80)
        
        events = Hlq.data.get("events", {})
        tickets = Hlq.data.get("tickets", {})
        
        print(f"剧目总数: {len(events)}")
        print(f"票务总数: {len(tickets)}")
        
        if events:
            print("\n最近的剧目示例:")
            for i, (eid, event) in enumerate(list(events.items())[:3]):
                print(f"  {i+1}. {event.get('title', 'N/A')} (ID: {eid})")
        
        # 测试3: 数据比对测试
        print("\n" + "="*80)
        print("📊 测试3: 数据比对测试")
        print("="*80)
        
        try:
            print("正在调用 Hlq.compare_to_database_async()...")
            result = await Hlq.compare_to_database_async()
            
            print("\n✅ 数据比对成功")
            print("\n变动统计:")
            categorized = result.get("categorized", {})
            total_changes = 0
            for cat, items in categorized.items():
                count = len(items)
                total_changes += count
                if count > 0:
                    emoji = {
                        "new": "🆕",
                        "add": "➕",
                        "pending": "⏰",
                        "return": "🔄",
                        "back": "📈",
                        "sold": "📉"
                    }
                    print(f"  {emoji.get(cat, '❓')} {cat}: {count} 条")
            
            if total_changes == 0:
                print("  ℹ️  当前没有票务变动")
            
            print(f"\n总变动数: {total_changes}")
            
        except Exception as e:
            print(f"❌ 数据比对失败: {e}")
            import traceback
            print(traceback.format_exc())
        
        # 测试4: 模拟消息生成
        if test_user_id:
            print("\n" + "="*80)
            print("📊 测试4: 模拟消息生成")
            print("="*80)
            
            # 需要一个 plugin 实例，这里无法直接创建
            # 所以只打印提示信息
            print("⚠️  此测试需要在 bot 运行时通过 /debug通知 mock 命令执行")
            print("或者在有 plugin 实例的环境中运行 run_debug_tests()")
        
        print("\n" + "="*80)
        print("✅ 快速测试完成")
        print("="*80)
        
        # 总结建议
        print("\n📋 调试建议:")
        if not users or not test_user_id:
            print("  ⚠️  没有用户数据，请先添加用户")
        else:
            if int(attention_mode) == 0:
                print("  ⚠️  测试用户的关注模式为0，不会收到任何通知")
                print("     建议: 使用 /呼啦圈通知 1 命令切换模式")
            else:
                print("  ✅ 用户关注模式已启用")
        
        if not events:
            print("  ⚠️  没有呼啦圈数据，请检查数据文件")
        else:
            print("  ✅ 呼啦圈数据正常")
        
        if total_changes == 0:
            print("  ℹ️  当前没有票务变动，这是正常的")
            print("     建议: 使用 /debug通知 mock 命令测试模拟数据")
        else:
            print(f"  🔥 检测到 {total_changes} 条票务变动")
            print("     如果没有收到通知，请检查定时任务是否运行")
        
    except ImportError as e:
        print(f"\n❌ 模块导入失败: {e}")
        print("请确保在项目根目录运行此脚本")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    print("\n提示: 此脚本需要在 bot 的数据已加载的情况下运行")
    print("建议在 bot 运行时使用 /debug通知 命令进行测试\n")
    
    # 运行测试
    asyncio.run(quick_test())
