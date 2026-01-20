#!/usr/bin/env python3
"""
数据库清理脚本 - 重置用户和订阅数据
WARNING: 此脚本会删除所有用户和订阅数据！仅在开发环境使用！
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

def cleanup_database():
    """清理数据库中的用户和订阅数据"""
    print("⚠️  警告：此操作将删除所有用户和订阅数据！")
    print("=" * 60)
    
    # 安全确认
    response = input("确认要清理数据库吗？(输入 'YES' 继续): ")
    if response != "YES":
        print("❌ 操作已取消")
        return
    
    print("\n🗑️  开始清理数据库...")
    
    with session_scope() as session:
        # 统计当前数据
        user_count = len(session.exec(select(User)).all())
        sub_count = len(session.exec(select(Subscription)).all())
        target_count = len(session.exec(select(SubscriptionTarget)).all())
        option_count = len(session.exec(select(SubscriptionOption)).all())
        auth_count = len(session.exec(select(UserAuthMethod)).all())
        
        print(f"\n📊 当前数据统计:")
        print(f"   - User: {user_count}")
        print(f"   - Subscription: {sub_count}")
        print(f"   - SubscriptionTarget: {target_count}")
        print(f"   - SubscriptionOption: {option_count}")
        print(f"   - UserAuthMethod: {auth_count}")
        
        # 按照外键依赖顺序删除
        print("\n🧹 删除数据...")
        
        # 1. 删除 SubscriptionTarget (依赖 Subscription)
        for target in session.exec(select(SubscriptionTarget)).all():
            session.delete(target)
        print(f"   ✓ 已删除 {target_count} 条 SubscriptionTarget")
        
        # 2. 删除 SubscriptionOption (依赖 Subscription)
        for option in session.exec(select(SubscriptionOption)).all():
            session.delete(option)
        print(f"   ✓ 已删除 {option_count} 条 SubscriptionOption")
        
        # 3. 删除 Subscription (依赖 User)
        for sub in session.exec(select(Subscription)).all():
            session.delete(sub)
        print(f"   ✓ 已删除 {sub_count} 条 Subscription")
        
        # 4. 删除 UserAuthMethod (依赖 User)
        for auth in session.exec(select(UserAuthMethod)).all():
            session.delete(auth)
        print(f"   ✓ 已删除 {auth_count} 条 UserAuthMethod")
        
        # 5. 删除 User
        for user in session.exec(select(User)).all():
            session.delete(user)
        print(f"   ✓ 已删除 {user_count} 条 User")
        
        session.commit()
        print("\n✨ 数据库清理完成！")
        
        # 重置 ID 计数器
        User.set_id_counter(0)
        print("🔢 User ID 计数器已重置为 0")
        
    print("\n✅ 现在可以运行 import_legacy_users.py 重新导入数据了\n")

if __name__ == "__main__":
    cleanup_database()
