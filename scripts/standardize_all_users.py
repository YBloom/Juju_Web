import logging
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from sqlmodel import Session, select, func
from services.db.connection import get_engine
from services.db.models import User, UserAuthMethod
from services.user_service import UserService

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def standardize_all_users():
    engine = get_engine()
    with Session(engine) as session:
        log.info("=== Starting Global User Standardization ===")
        
        # 1. Find all users with non-standard IDs (not 6 digits and not group_)
        # AND exclude users that are already inactive if we want, but better to process all active ones
        stmt = select(User).where(
            func.length(User.user_id) != 6,
            ~User.user_id.startswith("group_"),
            User.active == True
        )
        legacy_users = session.exec(stmt).all()
        
        log.info(f"🔍 Found {len(legacy_users)} legacy users to standardize.")
        
        migrated_count = 0
        
        for legacy_user in legacy_users:
            old_id = legacy_user.user_id # e.g. "3022402752"
            
            # Check if this QQ already has a mapping (from a previous partial move)
            stmt_auth = select(UserAuthMethod).where(
                UserAuthMethod.provider == "qq",
                UserAuthMethod.provider_user_id == old_id
            )
            existing_auth = session.exec(stmt_auth).first()
            
            if existing_auth:
                target_id = existing_auth.user_id
                log.info(f"🔗 Legacy user {old_id} already has a linked account {target_id}. Merging...")
            else:
                # Create a new standardized account
                target_id = User.generate_next_id(session)
                log.info(f"✨ Creating new standardized account {target_id} for legacy user {old_id}")
                
                new_user = User(
                    user_id=target_id,
                    nickname=legacy_user.nickname,
                    avatar_url=legacy_user.avatar_url,
                    email=legacy_user.email
                )
                session.add(new_user)
                
                # Create the auth mapping
                new_auth = UserAuthMethod(
                    user_id=target_id,
                    provider="qq",
                    provider_user_id=old_id,
                    is_primary=True
                )
                session.add(new_auth)
                session.flush() # Ensure target exists before merge
            
            # Perform merge
            try:
                svc = UserService(session)
                # Merge old legacy into new target
                success = svc.merge_users(
                    source_user_id=old_id, 
                    target_user_id=target_id, 
                    operator="global_migration"
                )
                if success:
                    migrated_count += 1
                    log.info(f"✅ Successfully standardized {old_id} -> {target_id}")
                else:
                    log.warning(f"⚠️ Standardization failed/skipped for {old_id}")
            except Exception as e:
                log.error(f"❌ Error standardizing {old_id}: {e}")
                session.rollback()
                # Re-fetch session state if needed, but best is to stop and investigate if DB error
                continue
                
        log.info(f"=== Migration Complete. Standardized {migrated_count} users. ===")

if __name__ == "__main__":
    standardize_all_users()
