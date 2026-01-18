#!/usr/bin/env python3
"""
通知引擎测试脚本 - 不影响正常服务
用法: python scripts/test_notification_engine.py
"""

import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db.init import init_db
from services.db.connection import session_scope
from services.db.models import SendQueue, SendQueueStatus, User, Subscription, SubscriptionTarget, SubscriptionOption
from services.hulaquan.service import HulaquanService
from services.hulaquan.models import TicketUpdate
from services.notification import NotificationEngine
from sqlmodel import select

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


class MockBotApi:
    """模拟 Bot API - 不实际发送消息"""
    
    async def post_private_msg(self, user_id, text):
        log.info(f"[MOCK] 发送私信给 {user_id}:\n{text[:200]}...")
        return {"status": "ok"}


async def test_subscription_matching():
    """测试订阅匹配逻辑"""
    log.info("=" * 50)
    log.info("测试 1: 订阅匹配逻辑")
    log.info("=" * 50)
    
    # 创建模拟的 TicketUpdate
    mock_updates = [
        TicketUpdate(
            ticket_id="test_001",
            event_id="12345",
            event_title="测试剧目《剧名》",
            change_type="new",
            message="🆕上新: 测试场次",
            session_time=None,
            price=280.0,
            stock=100,
            total_ticket=500,
            cast_names=["演员A", "演员B"],
        ),
        TicketUpdate(
            ticket_id="test_002",
            event_id="67890",
            event_title="另一个剧目",
            change_type="restock",
            message="♻️回流: 另一场次",
            session_time=None,
            price=380.0,
            stock=50,
            total_ticket=200,
            cast_names=["演员C"],
        ),
    ]
    
    engine = NotificationEngine(bot_api=MockBotApi())
    enqueued = await engine.process_updates(mock_updates)
    
    log.info(f"入队通知数: {enqueued}")
    return enqueued


async def test_queue_consumption():
    """测试队列消费 (使用 MockBotApi)"""
    log.info("=" * 50)
    log.info("测试 2: 队列消费 (Mock 发送)")
    log.info("=" * 50)
    
    engine = NotificationEngine(bot_api=MockBotApi())
    sent = await engine.consume_queue()
    
    log.info(f"Mock 发送数: {sent}")
    return sent


async def test_sync_without_send():
    """测试同步数据但不发送通知"""
    log.info("=" * 50)
    log.info("测试 3: 同步数据 (只入队不发送)")
    log.info("=" * 50)
    
    async with HulaquanService() as service:
        updates = await service.sync_all_data()
    
    log.info(f"同步检测到 {len(updates)} 条更新")
    
    if updates:
        # 只入队，不消费
        engine = NotificationEngine(bot_api=None)  # 不设置 api，consume_queue 会跳过
        enqueued = await engine.process_updates(updates)
        log.info(f"入队通知数: {enqueued}")
    
    return len(updates)


def show_queue_status():
    """显示当前队列状态"""
    log.info("=" * 50)
    log.info("当前 SendQueue 状态")
    log.info("=" * 50)
    
    with session_scope() as session:
        pending = session.exec(select(SendQueue).where(SendQueue.status == SendQueueStatus.PENDING)).all()
        sent = session.exec(select(SendQueue).where(SendQueue.status == SendQueueStatus.SENT)).all()
        failed = session.exec(select(SendQueue).where(SendQueue.status == SendQueueStatus.FAILED)).all()
        
        log.info(f"Pending: {len(pending)}")
        log.info(f"Sent:    {len(sent)}")
        log.info(f"Failed:  {len(failed)}")
        
        if pending:
            log.info("\n最近 5 条 Pending:")
            for item in pending[:5]:
                log.info(f"  - user_id={item.user_id}, scope={item.scope}, ref_id={item.ref_id}")


def show_subscription_stats():
    """显示订阅统计"""
    log.info("=" * 50)
    log.info("订阅统计")
    log.info("=" * 50)
    
    with session_scope() as session:
        subs = session.exec(select(Subscription)).all()
        targets = session.exec(select(SubscriptionTarget)).all()
        
        log.info(f"总订阅数: {len(subs)}")
        log.info(f"总目标数: {len(targets)}")
        
        # 按类型统计
        from collections import Counter
        kinds = Counter(t.kind for t in targets)
        for kind, count in kinds.items():
            log.info(f"  - {kind}: {count}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="通知引擎测试")
    parser.add_argument("--match", action="store_true", help="测试订阅匹配")
    parser.add_argument("--consume", action="store_true", help="测试队列消费 (Mock)")
    parser.add_argument("--sync", action="store_true", help="测试同步数据 (只入队)")
    parser.add_argument("--status", action="store_true", help="显示队列状态")
    parser.add_argument("--stats", action="store_true", help="显示订阅统计")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    
    args = parser.parse_args()
    
    # Init DB
    init_db()
    
    if args.all or not any([args.match, args.consume, args.sync, args.status, args.stats]):
        # 默认显示状态
        show_subscription_stats()
        show_queue_status()
    
    if args.match or args.all:
        await test_subscription_matching()
    
    if args.consume or args.all:
        await test_queue_consumption()
    
    if args.sync:
        await test_sync_without_send()
    
    if args.status:
        show_queue_status()
    
    if args.stats:
        show_subscription_stats()

if __name__ == "__main__":
    asyncio.run(main())
