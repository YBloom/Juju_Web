"""
Safe Remediation Script for Sync Issues.
1. Migrate legacy UserSession.user_id to canonical 6-digit IDs.
2. Synchronize User.global_notification_level with SubscriptionOption.notification_level safely.
"""
import logging
from sqlmodel import Session, select, func
from services.db.connection import get_engine
from services.db.models import User, UserAuthMethod, UserSession, Subscription, SubscriptionOption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remediate():
    engine = get_engine()
    with Session(engine) as session:
        # 1. Migrate UserSession
        logger.info("Checking UserSessions for legacy IDs...")
        sessions = session.exec(select(UserSession)).all()
        migrated_sessions = 0
        for s in sessions:
            if len(s.user_id) != 6 and not s.user_id.startswith("group_"):
                auth = session.exec(select(UserAuthMethod).where(UserAuthMethod.provider_user_id == s.user_id)).first()
                if auth:
                    logger.info(f"  - Migrating Session {s.session_id[:6]}... from {s.user_id} to {auth.user_id}")
                    s.user_id = auth.user_id
                    session.add(s)
                    migrated_sessions += 1
        
        # 2. Sync Notification Levels
        logger.info("Synchronizing notification levels safely...")
        active_users = session.exec(select(User).where(func.length(User.user_id) == 6)).all()
        synced_count = 0
        for user in active_users:
            sub = session.exec(select(Subscription).where(Subscription.user_id == user.user_id)).first()
            if not sub: continue
            
            opt = session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)).first()
            
            # 策略：取两者中的最大值 (0是关闭，1-5是开启)
            # 如果 web 是 0 但 bot 是 2，说明 bot 曾经设置过，应保留 2
            current_user_level = user.global_notification_level or 0
            current_opt_level = opt.notification_level if opt else 2 # 默认2
            
            final_level = max(current_user_level, current_opt_level)
            
            changed = False
            if user.global_notification_level != final_level:
                user.global_notification_level = final_level
                session.add(user)
                changed = True
            
            if not opt:
                opt = SubscriptionOption(subscription_id=sub.id, notification_level=final_level)
                session.add(opt)
                changed = True
            elif opt.notification_level != final_level:
                opt.notification_level = final_level
                session.add(opt)
                changed = True
                
            if changed:
                logger.info(f"  - User {user.user_id} level synced to {final_level}")
                synced_count += 1
        
        session.commit()
        logger.info(f"=== Remediation Complete. Migrated {migrated_sessions} sessions, synced {synced_count} levels. ===")

if __name__ == "__main__":
    remediate()
