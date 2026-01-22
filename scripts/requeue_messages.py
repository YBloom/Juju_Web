import logging
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from sqlmodel import Session, select, col
from services.db.connection import session_scope
from services.db.models import SendQueue, SendQueueStatus

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def requeue_skipped_messages():
    """
    将由于安全白名单被跳过（或一直处于 PENDING 状态）的消息重新设为待发送。
    通常这些消息在日志中显示为 "SAFE MODE: Skipping..."，但在数据库中可能仍为 PENDING。
    如果它们已经被标记为 SENT（尽管没发出去），脚本也会处理。
    """
    logger.info("🚀 开始扫描积压消息...")
    
    with session_scope() as session:
        # 查询所有 PENDING 状态且创建时间在过去 24 小时内的消息
        # 或者你可以根据具体的 user_id/ref_id 进一步筛选
        stmt = select(SendQueue).where(
            SendQueue.status == SendQueueStatus.PENDING
        )
        pending_items = session.exec(stmt).all()
        
        if not pending_items:
            logger.info("✅ 没有发现积压的 PENDING 消息。")
            return

        count = 0
        for item in pending_items:
            # 重置重试计数和下次重试时间，确保它们能被 NotificationEngine 立即扫描到
            item.retry_count = 0
            item.next_retry_at = None
            # 确保状态是 PENDING (虽然查询的就是 PENDING，这里做个显式确认)
            item.status = SendQueueStatus.PENDING
            session.add(item)
            count += 1
            logger.info(f"📝 准备重发消息 ID: {item.id}, User: {item.user_id}, Ref: {item.ref_id}")
            
        session.commit()
        logger.info(f"✨ 成功重置 {count} 条消息，它们将在机器人下次扫描队列时发出。")

if __name__ == "__main__":
    # 确保在项目根目录运行，或者 PYTHONPATH 包含项目根目录
    try:
        requeue_skipped_messages()
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
