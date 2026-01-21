
import logging
import sys
import uuid
from sqlmodel import select
from services.db.connection import session_scope
from services.db.models import User, Subscription, SubscriptionOption, SubscriptionTarget, SubscriptionFrequency
from services.user_service import UserService

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_user_service_merge():
    logger.info("🧪 Testing UserService.merge_users with Unified Config...")
    
    with session_scope() as session:
        # Create Source User (with custom settings)
        source_id = "999001"
        target_id = "999002"
        
        # Cleanup
        for uid in [source_id, target_id]:
            u = session.get(User, uid)
            if u:
                session.delete(u)
        session.commit()
        
        # Create Source
        source = User(
            user_id=source_id, 
            nickname="Source", 
            global_notification_level=4, 
            is_muted=True,
            silent_hours="23:00-08:00"
        )
        session.add(source)
        
        # Create Target (Default settings)
        target = User(
            user_id=target_id, 
            nickname="Target", 
            global_notification_level=0, # Default
            is_muted=False
        )
        session.add(target)
        session.commit()
        
        # Perform Merge
        svc = UserService(session)
        success = svc.merge_users(source_id, target_id)
        
        if not success:
            logger.error("❌ Merge failed!")
            return False
            
        session.refresh(target)
        
        # Verify Target inherited settings
        errors = []
        if target.global_notification_level != 4:
            errors.append(f"Global level mismatch: expected 4, got {target.global_notification_level}")
        if not target.is_muted:
            errors.append("Mute status mismatch: expected True")
        if target.silent_hours != "23:00-08:00":
            errors.append(f"Silent hours mismatch: expected '23:00-08:00', got {target.silent_hours}")
            
        if errors:
            for e in errors:
                logger.error(f"❌ {e}")
            return False
            
        logger.info("✅ UserService merge verified successfully!")
        return True

def test_model_fields():
    logger.info("🧪 Testing User model fields persistence...")
    with session_scope() as session:
        uid = "999003"
        u = session.get(User, uid)
        if u: session.delete(u)
        
        user = User(
            user_id=uid,
            notification_freq=SubscriptionFrequency.DAILY,
            global_notification_level=5
        )
        session.add(user)
        session.commit()
        
        session.refresh(user)
        if user.notification_freq != SubscriptionFrequency.DAILY:
             logger.error(f"❌ Freq mismatch: {user.notification_freq}")
             return False
        if user.global_notification_level != 5:
             logger.error(f"❌ Level mismatch: {user.global_notification_level}")
             return False
             
        logger.info("✅ User model fields persistence verified!")
        return True

if __name__ == "__main__":
    success = True
    try:
        if not test_model_fields(): success = False
        if not test_user_service_merge(): success = False
    except Exception as e:
        logger.error(f"❌ Exception during verification: {e}")
        import traceback
        traceback.print_exc()
        success = False
        
    if success:
        logger.info("🚀 All verification tests passed for Config Unification!")
        sys.exit(0)
    else:
        logger.error("💥 Verification failed!")
        sys.exit(1)
