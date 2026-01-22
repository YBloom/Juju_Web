import logging
import os
import sys
import json
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlmodel import Session, select
from services.db.connection import session_scope
from services.db.models import SendQueue, SendQueueStatus

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 从本地提取的积压消息数据 (Hardcoded from local DB)
PENDING_MESSAGES_DATA = [
    {"user_id":"000162","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "restock", "message": "♻️回流: 《奥尔菲斯》2026 02-07 19:30￥180（原价￥280) 学生票 余票1/20", "ticket_id": "36300"}]},"ref_id":"batch_36300_2026012213"},
    {"user_id":"000184","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "restock", "message": "♻️回流: 《奥尔菲斯》2026 02-07 19:30￥180（原价￥280) 学生票 余票1/20", "ticket_id": "36300"}]},"ref_id":"batch_36300_2026012213"},
    {"user_id":"000162","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "new", "message": "🆕上新: 《奥尔菲斯》2026 01-29 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36581"}, {"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "new", "message": "🆕上新: 《奥尔菲斯》2026 02-04 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36582"}]},"ref_id":"batch_36581_2026012214"},
    {"user_id":"000184","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "new", "message": "🆕上新: 《奥尔菲斯》2026 01-29 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36581"}, {"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "new", "message": "🆕上新: 《奥尔菲斯》2026 02-04 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36582"}]},"ref_id":"batch_36581_2026012214"},
    {"user_id":"000162","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "back", "message": "➕票增: 《奥尔菲斯》2026 02-04 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36582"}]},"ref_id":"batch_36582_2026012217"},
    {"user_id":"000184","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "back", "message": "➕票增: 《奥尔菲斯》2026 02-04 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36582"}]},"ref_id":"batch_36582_2026012217"},
    {"user_id":"000044","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3807", "event_title": "音乐剧《时光代理人》", "change_type": "back", "message": "➕票增: 《时光代理人》02-01 19:30 ￥199 学生票 余票17/20", "ticket_id": "35403"}]},"ref_id":"batch_35403_2026012217"},
    {"user_id":"000076","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3807", "event_title": "音乐剧《时光代理人》", "change_type": "back", "message": "➕票增: 《时光代理人》02-01 19:30 ￥199 学生票 余票17/20", "ticket_id": "35403"}]},"ref_id":"batch_35403_2026012217"},
    {"user_id":"000162","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "back", "message": "➕票增: 《奥尔菲斯》2026 02-04 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36582"}]},"ref_id":"batch_36582_2026012218"},
    {"user_id":"000184","channel":"qq_private","scope":"ticket_update","payload":{"updates": [{"event_id": "3928", "event_title": "惊悚推理悬疑音乐剧《奥尔菲斯》", "change_type": "back", "message": "➕票增: 《奥尔菲斯》2026 02-04 19:30￥180（原价￥280) 学生票 余票20/20", "ticket_id": "36582"}]},"ref_id":"batch_36582_2026012218"}
]

def restore_messages():
    """
    将提取的积压消息插入数据库，并生成新的 ref_id 以避免被系统去重拦截。
    """
    logger.info(f"🚀 开始恢复 {len(PENDING_MESSAGES_DATA)} 条积压消息...")
    
    with session_scope() as session:
        restored_count = 0
        for data in PENDING_MESSAGES_DATA:
            # 修改 ref_id 防止被去重 (增加 _restored 后缀)
            original_ref = data["ref_id"]
            new_ref = f"{original_ref}_restored_{datetime.now().strftime('%M%S')}"
            
            # 创建新对象
            new_item = SendQueue(
                user_id=data["user_id"],
                channel=data["channel"],
                scope=data["scope"],
                payload=data["payload"], # SQLModel 应该会自动处理 JSON
                status=SendQueueStatus.PENDING,
                ref_id=new_ref,
                retry_count=0,
                next_retry_at=None, # 立即发送
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(new_item)
            restored_count += 1
            logger.info(f"➕ 已插入: User {data['user_id']} | Ref: {new_ref}")
            
        session.commit()
        logger.info(f"✨ 成功插入 {restored_count} 条消息！它们将在下一次轮询中被发送。")

if __name__ == "__main__":
    try:
        restore_messages()
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
