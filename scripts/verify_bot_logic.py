import asyncio
from unittest.mock import AsyncMock, MagicMock
from ncatbot.core import BaseMessage
from plugins.Hulaquan.main import Hulaquan

async def verify_bot_logic():
    print("=== Bot Logic Verification ===")
    print("=== Bot 逻辑验证 ===")
    
    # 1. Setup Mock Plugin
    # 1. 设置模拟插件
    # Hulaquan needs event_bus and time_task_scheduler
    # Hulaquan 需要 event_bus 和 time_task_scheduler
    event_bus = MagicMock()
    scheduler = MagicMock()
    plugin = Hulaquan(event_bus=event_bus, time_task_scheduler=scheduler)
    plugin.api = AsyncMock() # Mock the bot API
    
    # 2. Test Search Command
    # 2. 测试搜索命令
    print("\n[Test 1] Mocking /hlq 连璧 search...")
    print("\n[Test 1] 模拟 /hlq 连璧 搜索...")
    msg = MagicMock(spec=BaseMessage)
    msg.raw_message = "/hlq 连璧"
    msg.user_id = "test_user"
    msg.reply_text = AsyncMock()
    
    await plugin.on_hlq_search(msg)
    
    # Check if reply_text was called
    if msg.reply_text.called:
        print("Bot replied with search results:")
        for call in msg.reply_text.call_args_list:
            print(f"  > {call.args[0][:100]}...")
    else:
        print("Bot failed to reply to search.")

    # 3. Test Date Command
    # 3. 测试日期命令
    print("\n[Test 2] Mocking /date 2026-01-10...")
    print("\n[Test 2] 模拟 /date 2026-01-10...")
    msg_date = MagicMock(spec=BaseMessage)
    msg_date.raw_message = "/date 2026-01-10"
    msg_date.user_id = "test_user"
    msg_date.reply_text = AsyncMock()
    
    await plugin.on_list_hulaquan_events_by_date(msg_date)
    if msg_date.reply_text.called:
        print("Bot replied with date results:")
        print(f"  > {msg_date.reply_text.call_args[0][0][:200]}...")
    else:
        print("Bot failed to reply to date query.")

    print("\n=== Verification Finished ===")

if __name__ == "__main__":
    asyncio.run(verify_bot_logic())
