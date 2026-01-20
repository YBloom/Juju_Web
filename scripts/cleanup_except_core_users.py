#!/usr/bin/env python3
"""
选择性数据库清理脚本 - 保留核心用户 (000001, 000002)
WARNING: 此脚本会删除除 000001 和 000002 以外的所有用户数据！
"""
import os
import sys

sys.path.append(os.getcwd())

from services.db.connection import session_scope
from services.db.models import (
    User, 
    Subscription, 
    SubscriptionTarget, 
    SubscriptionOption, 
    UserAuthMethod
)
from sqlmodel import select

# 要保留的用户 ID
PRESERVED_USER_IDS = {'000001', '000002'}

def selective_cleanup(db_path=None, force=False):
    """选择性清理数据库，保留指定用户"""
    print("⚠️  警告：此操作将删除除 000001 和 000002 以外的所有用户数据！")
    print("=" * 60)
    
    # 安全确认
    if not force:
        response = input("确认要清理数据库吗？(输入 'YES' 继续): ")
        if response != "YES":
            print("❌ 操作已取消")
            return
    else:
        print("⏩ 检测到 --force 标志，跳过确认...")
    
    print("\n🗑️  开始选择性清理数据库...")
    
    with session_scope(db_path) as session:
        # 统计当前数据
        all_users = session.exec(select(User)).all()
        preserved_users = [u for u in all_users if u.user_id in PRESERVED_USER_IDS]
        to_delete_users = [u for u in all_users if u.user_id not in PRESERVED_USER_IDS]
        
        print(f"\n📊 当前数据统计:")
        print(f"   - 总用户数: {len(all_users)}")
        print(f"   - 保留用户: {len(preserved_users)} ({', '.join(PRESERVED_USER_IDS)})")
        print(f"   - 待删除用户: {len(to_delete_users)}")
        
        if len(to_delete_users) == 0:
            print("\n✅ 没有需要删除的用户")
            return
        
        # 显示保留的用户信息
        print(f"\n🔒 将保留以下用户:")
        for u in preserved_users:
            print(f"   - {u.user_id}: {u.nickname or '(无昵称)'} ({u.email or '无邮箱'})")
        
        stats = {
            'users': 0,
            'subscriptions': 0,
            'targets': 0,
            'options': 0,
            'auths': 0
        }
        
        # 开始删除
        print(f"\n🧹 删除 {len(to_delete_users)} 个用户及其相关数据...")
        
        for user in to_delete_users:
            user_id = user.user_id
            
            # 1. 获取该用户的所有订阅
            user_subs = session.exec(select(Subscription).where(Subscription.user_id == user_id)).all()
            
            for sub in user_subs:
                # 删除 SubscriptionTarget
                targets = session.exec(select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)).all()
                for t in targets:
                    session.delete(t)
                    stats['targets'] += 1
                
                # 删除 SubscriptionOption
                options = session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)).all()
                for o in options:
                    session.delete(o)
                    stats['options'] += 1
                
                # 删除 Subscription
                session.delete(sub)
                stats['subscriptions'] += 1
            
            # 2. 删除 UserAuthMethod
            auths = session.exec(select(UserAuthMethod).where(UserAuthMethod.user_id == user_id)).all()
            for auth in auths:
                session.delete(auth)
                stats['auths'] += 1
            
            # 3. 删除 User
            session.delete(user)
            stats['users'] += 1
        
        session.commit()
        print("\n✨ 数据库清理完成！")
        
        # 显示删除统计
        print(f"\n📊 删除统计:")
        print(f"   - 用户: {stats['users']}")
        print(f"   - 认证绑定: {stats['auths']}")
        print(f"   - 订阅集: {stats['subscriptions']}")
        print(f"   - 订阅选项: {stats['options']}")
        print(f"   - 订阅目标: {stats['targets']}")
        
        # 重置 ID 计数器为 2 (下一个生成的 ID 将是 000003)
        User.set_id_counter(2)
        print("\n🔢 User ID 计数器已重置为 2 (下一个 ID: 000003)")
        
    print("\n✅ 现在可以运行 import_legacy_users.py 重新导入其他用户了\n")

if __name__ == "__main__":
    import sys
    db_arg = None
    force_arg = False
    
    for arg in sys.argv[1:]:
        if arg == "--force":
            force_arg = True
        elif not db_arg:
            db_arg = arg
            
    selective_cleanup(db_arg, force_arg)
