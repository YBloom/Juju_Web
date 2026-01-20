import logging
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select
from services.db.models import User, Subscription, SubscriptionTarget, SubscriptionOption, UserAuthMethod, AccountMergeLog

log = logging.getLogger(__name__)

class UserService:
    def __init__(self, session: Session):
        self.session = session

    def merge_users(self, source_user_id: str, target_user_id: str, operator: str = "system") -> bool:
        """
        Merge source_user into target_user.
        Moves Subscriptions, AuthMethods, and other data.
        Soft-deletes source_user.
        """
        if source_user_id == target_user_id:
            return False

        source_user = self.session.get(User, source_user_id)
        target_user = self.session.get(User, target_user_id)

        if not source_user or not target_user:
            log.error(f"Cannot merge: Source {source_user_id} or Target {target_user_id} not found.")
            return False

        log.info(f"🔄 Merging User {source_user_id} -> {target_user_id}")
        
        # 1. Merge Subscriptions
        # Strategy: If target has no subscription, move source's subscription to target.
        # If target HAS subscription, move source's TARGETS to target's subscription.
        
        source_sub = self.session.exec(select(Subscription).where(Subscription.user_id == source_user_id)).first()
        target_sub = self.session.exec(select(Subscription).where(Subscription.user_id == target_user_id)).first()
        
        subs_count = 0
        
        if source_sub:
            if not target_sub:
                # Direct ownership transfer
                source_sub.user_id = target_user_id
                self.session.add(source_sub)
                target_sub = source_sub # For reference
                log.info(f"  - Moved Subscription {source_sub.id} to {target_user_id}")
            else:
                # Merge items
                log.info(f"  - Merging items from Subscription {source_sub.id} to {target_sub.id}")
                
                # Move Targets
                source_targets = self.session.exec(select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == source_sub.id)).all()
                for t in source_targets:
                    # Check duplication on target
                    exists = self.session.exec(select(SubscriptionTarget).where(
                        SubscriptionTarget.subscription_id == target_sub.id,
                        SubscriptionTarget.kind == t.kind,
                        SubscriptionTarget.target_id == t.target_id
                    )).first()
                    
                    if not exists:
                        t.subscription_id = target_sub.id
                        self.session.add(t)
                        subs_count += 1
                    else:
                        # Duplicate, just delete source target or keep existing?
                        # Keep existing target's setting, maybe update flags?
                        # For now, discard duplicate from source (delete later with source_sub)
                        self.session.delete(t)
                
                # Cleanup source options to allow deleting subscription
                source_opt = self.session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == source_sub.id)).first()
                if source_opt:
                    # If target has no options, maybe we should move them?
                    # But simpler to just keep target (or default) and delete source for now.
                    # Or check if target has options
                    target_opt = self.session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == target_sub.id)).first()
                    if not target_opt:
                         source_opt.subscription_id = target_sub.id
                         self.session.add(source_opt)
                    else:
                         self.session.delete(source_opt)
                
                # Delete source subscription shell
                self.session.delete(source_sub)

        # 2. Merge Auth Methods
        auths = self.session.exec(select(UserAuthMethod).where(UserAuthMethod.user_id == source_user_id)).all()
        for auth in auths:
            # Check if target already has this provider
            exists = self.session.exec(select(UserAuthMethod).where(
                UserAuthMethod.user_id == target_user_id,
                UserAuthMethod.provider == auth.provider
            )).first()
            
            if not exists:
                auth.user_id = target_user_id
                self.session.add(auth)
                log.info(f"  - Moved AuthMethod {auth.provider} to {target_user_id}")
            else:
                log.warn(f"  - Conflict: Target already has {auth.provider}, removing source auth.")
                self.session.delete(auth)

        # 3. Mark Source as Deleted / Inactive
        source_user.active = False
        # (Optional: Rename source ID to avoid future collisions? No, soft delete handles it.)
        self.session.add(source_user)
        
        # 4. Log
        merge_log = AccountMergeLog(
            source_user_id=source_user_id,
            target_user_id=target_user_id,
            merged_at=datetime.now(),
            subscriptions_count=subs_count,
            operator=operator
        )
        self.session.add(merge_log)
        
        self.session.commit()
        return True
