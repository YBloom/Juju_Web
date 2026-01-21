"""
Migrate settings from SubscriptionOption to User table.
将配置从冗余的 SubscriptionOption 表迁移到 User 表。
使用 Raw SQL 以避免 Enum 映射问题。
"""
import logging
import sys
import os

sys.path.append(os.getcwd())

from sqlalchemy import text
from services.db.connection import get_engine

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def migrate_settings():
    engine = get_engine()
    logger.info("🚀 开始迁移配置数据至 User 表 (Raw SQL)...")
    
    with engine.connect() as conn:
        # 1. 获取所有需要迁移的数据
        # select user_id, notification_level, freq, mute, allow_broadcast, silent_hours, last_notified_at
        sql_select = text("""
            SELECT 
                s.user_id, 
                so.notification_level, 
                so.freq, 
                so.mute, 
                so.allow_broadcast, 
                so.silent_hours, 
                so.last_notified_at
            FROM subscription s
            JOIN subscriptionoption so ON s.id = so.subscription_id
        """)
        
        results = conn.execute(sql_select).fetchall()
        logger.info(f"  - 找到 {len(results)} 条待迁移配置")
        
        # 2. 逐条更新 User 表
        count = 0
        for row in results:
            user_id, level, freq, mute, allow_broadcast, silent_hours, last_notified = row
            
            # 简单的 mapping 修正（如果需要）
            # 数据库里已经是存储的值了，直接搬运即可
            
            sql_update = text("""
                UPDATE user 
                SET 
                    global_notification_level = :level,
                    notification_freq = :freq,
                    is_muted = :mute,
                    allow_broadcast = :allow_broadcast,
                    silent_hours = :silent_hours,
                    last_notified_at = :last_notified
                WHERE user_id = :user_id
            """)
            
            conn.execute(sql_update, {
                "level": level,
                "freq": freq,
                "mute": mute,
                "allow_broadcast": allow_broadcast,
                "silent_hours": silent_hours,
                "last_notified": last_notified,
                "user_id": user_id
            })
            count += 1
            
        conn.commit()
        logger.info(f"✅ 成功迁移 {count} 个用户的配置。")

if __name__ == "__main__":
    migrate_settings()
