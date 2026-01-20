#!/usr/bin/env python3
"""
历史用户订阅数据导入脚本
从 UsersManager.json 导入旧系统的订阅数据到新系统
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 将项目根目录添加到路径
sys.path.append(os.getcwd())

from services.db.connection import session_scope
from services.db.models import User, Subscription, SubscriptionTarget, SubscriptionOption, UserAuthMethod
from sqlmodel import select

# 数据文件路径
LEGACY_JSON = "plugins_legacy/data_legacy_260118_final/data/data_manager/UsersManager.json"

# Mode Mapping: Legacy 0/1/2/3 -> New 0/2/3/5
# 旧系统: "1"=上新, "2"=上新+补票+回流, "3"=全量
# 新系统: 0=关闭, 1=上新, 2=上新+补票, 3=上新+补票+回流, 4=+票减, 5=全量
MODE_MAPPING = {
    0: 0,
    1: 2,  # 上新/补票
    2: 3,  # 上新/补票/回流
    3: 5,  # 全量 (包含余票增减)
}

def import_users(db_path: str = None):
    """导入历史用户数据"""
    print(f"📖 正在读取历史数据: {LEGACY_JSON}")
    if not Path(LEGACY_JSON).exists():
        print(f"❌ 文件不存在: {LEGACY_JSON}")
        return
    
    with open(LEGACY_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    users_data = data.get('users', {})
    print(f"   发现 {len(users_data)} 个历史用户")
    
    stats = {
        'users_created': 0,
        'auth_methods_created': 0,
        'subs_created': 0,
        'events_added': 0,
        'actors_added': 0,
        'skipped_inactive': 0
    }
    
    with session_scope(db_path) as session:
        # 初始化 ID 计数器
        existing_users = session.exec(select(User)).all()
        if existing_users:
            max_id = 0
            for u in existing_users:
                try:
                    uid_int = int(u.user_id)
                    if uid_int > max_id:
                        max_id = uid_int
                except ValueError:
                    continue
            User.set_id_counter(max_id)
            print(f"🔢 ID 计数器已初始化，从 {max_id + 1:06d} 开始生成")

        print("\n🚀 开始导入数据...")
        
        for qq_id, user_info in users_data.items():
            # 检查用户激活状态
            if not user_info.get('activate', False):
                stats['skipped_inactive'] += 1
                continue
            
            # 1. 检查是否已经存在该 QQ 的绑定 (通过 UserAuthMethod)
            existing_auth = session.exec(
                select(UserAuthMethod).where(UserAuthMethod.provider_user_id == str(qq_id), UserAuthMethod.provider == "qq")
            ).first()
            
            if existing_auth:
                user = session.get(User, existing_auth.user_id)
                new_user_id = user.user_id
                print(f"ℹ️ 用户 QQ:{qq_id} 已存在 (ID:{new_user_id})，跳过创建")
            else:
                # 2. 创建新 User
                new_user_id = User.generate_next_id()
                attention_mode = MODE_MAPPING.get(int(user_info.get('attention_to_hulaquan', 0)), 0)
                
                user = User(
                    user_id=new_user_id,
                    nickname=f"QQ用户_{str(qq_id)[-4:]}",
                    active=True,
                    trust_score=100,
                    global_notification_level=attention_mode,
                    bot_interaction_mode="hybrid"
                )
                session.add(user)
                stats['users_created'] += 1
                
                # 3. 创建 UserAuthMethod 关联
                auth_method = UserAuthMethod(
                    user_id=new_user_id,
                    provider_user_id=str(qq_id),
                    provider="qq",
                    is_primary=True
                )
                session.add(auth_method)
                stats['auth_methods_created'] += 1

            # 4. 确保 Subscription 记录存在
            sub = session.exec(select(Subscription).where(Subscription.user_id == new_user_id)).first()
            if not sub:
                sub = Subscription(user_id=new_user_id)
                session.add(sub)
                session.flush() # 获取 sub.id
                stats['subs_created'] += 1
            
            # 5. 设置 SubscriptionOption
            attention_mode = MODE_MAPPING.get(int(user_info.get('attention_to_hulaquan', 0)), 0)
            if attention_mode > 0:
                opt = session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)).first()
                if not opt:
                    opt = SubscriptionOption(
                        subscription_id=sub.id,
                        notification_level=attention_mode,
                        freq="REALTIME"
                    )
                    session.add(opt)
            
            # 6. 导入订阅目标
            subscribe_obj = user_info.get('subscribe', {})
            
            # 剧目订阅 (PLAY)
            for event in subscribe_obj.get('subscribe_events', []):
                target_id = str(event.get('id'))
                existing_t = session.exec(
                    select(SubscriptionTarget).where(
                        SubscriptionTarget.subscription_id == sub.id,
                        SubscriptionTarget.kind == "PLAY",
                        SubscriptionTarget.target_id == target_id
                    )
                ).first()
                
                if not existing_t:
                    target = SubscriptionTarget(
                        subscription_id=sub.id,
                        kind="PLAY",
                        target_id=target_id
                    )
                    session.add(target)
                    stats['events_added'] += 1
            
            # 演员订阅 (ACTOR)
            for actor in subscribe_obj.get('subscribe_actors', []):
                actor_name = actor.get('actor')
                include_events = actor.get('include_events', [])
                
                existing_t = session.exec(
                    select(SubscriptionTarget).where(
                        SubscriptionTarget.subscription_id == sub.id,
                        SubscriptionTarget.kind == "ACTOR",
                        SubscriptionTarget.target_id == actor_name
                    )
                ).first()
                
                if not existing_t:
                    target = SubscriptionTarget(
                        subscription_id=sub.id,
                        kind="ACTOR",
                        target_id=actor_name,
                        name=actor_name,
                        include_plays=include_events if include_events else None
                    )
                    session.add(target)
                    stats['actors_added'] += 1
        
        session.commit()
        print("\n✨ 导入完成！")
        
        # 显示统计
        print("\n📊 导入统计:")
        print(f"   - 创建用户: {stats['users_created']}")
        print(f"   - 创建认证绑定: {stats['auth_methods_created']}")
        print(f"   - 创建订阅集: {stats['subs_created']}")
        print(f"   - 导入剧目订阅: {stats['events_added']}")
        print(f"   - 导入演员订阅: {stats['actors_added']}")
        print(f"   - 跳过未激活用户: {stats['skipped_inactive']}")


if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("历史用户订阅数据导入工具 (V2 - 统一 6 位 ID版)")
    print("=" * 60)
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    try:
        import_users(db_path)
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
    print("=" * 60)
