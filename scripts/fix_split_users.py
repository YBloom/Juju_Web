import logging
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from sqlmodel import Session, select
from services.db.connection import get_engine
from services.db.models import User, UserAuthMethod
from services.user_service import UserService

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def fix_split_users():
    engine = get_engine()
    with Session(engine) as session:
        log.info("=== Starting Split User Remediation ===")
        
        # Find all QQ auth methods
        auths = session.exec(select(UserAuthMethod).where(UserAuthMethod.provider == "qq")).all()
        
        merged_count = 0
        
        for auth in auths:
            qq_id = auth.provider_user_id
            linked_user_id = auth.user_id # The New User ID (e.g. 000001 or 391xxxx...)
            
            # Check if a Legacy User exists with the QQ ID
            legacy_user = session.exec(select(User).where(User.user_id == qq_id)).first()
            
            if legacy_user:
                # We found a split!
                # Legacy User: qq_id
                # New User: linked_user_id
                
                # Double check they are not the same (shouldn't be, but valid check)
                if legacy_user.user_id == linked_user_id:
                    continue
                    
                log.info(f"🔧 Fixing Split: Legacy({qq_id}) -> New({linked_user_id})")
                
                try:
                    svc = UserService(session)
                    success = svc.merge_users(source_user_id=qq_id, target_user_id=linked_user_id, operator="fix_script")
                    if success:
                        merged_count += 1
                        log.info(f"✅ Successfully merged {qq_id} -> {linked_user_id}")
                    else:
                        log.warn(f"⚠️ Merge failed/skipped for {qq_id}")
                except Exception as e:
                    log.error(f"❌ Error merging {qq_id}: {e}")
                    session.rollback()
                    
        log.info(f"=== Remediation Complete. Merged {merged_count} users. ===")

if __name__ == "__main__":
    fix_split_users()
