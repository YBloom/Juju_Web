"""
Remediation script for config parity issues.
修复由 system_diagnose.py 发现的级别不一致点。
"""
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from services.db.connection import get_engine
from services.db.models import User, Subscription, SubscriptionOption

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_remediation():
    engine = get_engine()
    logger.info("🔧 开始修复跨平台配置同步不一致点...")
    
    with Session(engine) as session:
        # 1. 修复 User 与 SubscriptionOption 不一致
        # 策略：以 User 表为准（用户在 Web 端或最近一次 Bot 命令设置的值）
        stmt = (
            select(User, SubscriptionOption)
            .join(Subscription, User.user_id == Subscription.user_id)
            .join(SubscriptionOption, Subscription.id == SubscriptionOption.subscription_id)
        )
        results = session.exec(stmt).all()
        
        fixed_count = 0
        for user, opt in results:
            if user.global_notification_level != opt.notification_level:
                logger.info(f"  - 修复用户 {user.user_id}: BotOption {opt.notification_level} -> {user.global_notification_level}")
                opt.notification_level = user.global_notification_level
                session.add(opt)
                fixed_count += 1
        
        # 2. 修复新用户初始级别异常 (预期为 0)
        # 发现 000001 是 4
        users_to_fix = session.exec(select(User).where(User.user_id == '000001')).all()
        for u in users_to_fix:
            if u.global_notification_level != 0:
                logger.info(f"  - 修复新用户 {u.user_id} 初始级别: {u.global_notification_level} -> 0")
                u.global_notification_level = 0
                session.add(u)
                fixed_count += 1
        
        session.commit()
        logger.info(f"✅ 修复完成，共处理 {fixed_count} 处差异。")

if __name__ == "__main__":
    run_remediation()
