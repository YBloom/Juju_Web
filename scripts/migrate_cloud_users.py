#!/usr/bin/env python3
"""
云端用户数据一键迁移脚本
====================================
功能：
1. 自动备份当前数据库
2. 保留核心用户 (000001, 000002)
3. 清理并重新导入历史用户数据
4. 生成迁移报告

使用方法：
    python3.12 migrate_cloud_users.py [--force]
    
参数：
    --force    跳过确认提示，直接执行
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.db.connection import session_scope
from services.db.models import (
    User, 
    Subscription, 
    SubscriptionTarget, 
    SubscriptionOption, 
    UserAuthMethod
)
from sqlmodel import select

# 配置
PRESERVED_USER_IDS = {'000001', '000002'}
LEGACY_JSON = "plugins_legacy/data_legacy_260118_final/data/data_manager/UsersManager.json"
DB_PATH = "data/musicalbot.db"

MODE_MAPPING = {
    0: 0,  # 关闭
    1: 2,  # 重要 -> 新+补
    2: 3,  # 需要关注 -> 新+补+回
    3: 5,  # 全量
}

class MigrationReport:
    def __init__(self):
        self.backup_path = None
        self.preserved_users = []
        self.deleted_count = 0
        self.imported_count = 0
        self.errors = []
        
    def print_summary(self):
        print("\n" + "=" * 60)
        print("📋 迁移报告")
        print("=" * 60)
        print(f"备份文件: {self.backup_path}")
        print(f"\n保留用户: {len(self.preserved_users)} 个")
        for u in self.preserved_users:
            print(f"  - {u['user_id']}: {u['nickname']} ({u['email'] or '无邮箱'})")
        print(f"\n删除用户: {self.deleted_count} 个")
        print(f"导入用户: {self.imported_count} 个")
        
        if self.errors:
            print(f"\n⚠️  发现 {len(self.errors)} 个错误:")
            for err in self.errors:
                print(f"  - {err}")
        else:
            print("\n✅ 迁移成功，无错误")
        print("=" * 60)

def backup_database():
    """备份数据库"""
    print("\n📦 步骤 1: 备份数据库...")
    
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(f"数据库文件不存在: {DB_PATH}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    backup_path = backup_dir / f"musicalbot_before_migration_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    
    print(f"✅ 备份完成: {backup_path}")
    return str(backup_path)

def get_preserved_users_info():
    """获取要保留的用户信息"""
    with session_scope() as session:
        preserved = []
        for uid in PRESERVED_USER_IDS:
            user = session.get(User, uid)
            if user:
                preserved.append({
                    'user_id': user.user_id,
                    'nickname': user.nickname,
                    'email': user.email
                })
        return preserved

def cleanup_users():
    """清理用户数据（保留核心用户）"""
    print("\n🗑️  步骤 2: 清理用户数据（保留 000001, 000002）...")
    
    deleted_count = 0
    
    with session_scope() as session:
        all_users = session.exec(select(User)).all()
        to_delete = [u for u in all_users if u.user_id not in PRESERVED_USER_IDS]
        
        print(f"   发现 {len(all_users)} 个用户，将删除 {len(to_delete)} 个")
        
        for user in to_delete:
            user_id = user.user_id
            
            # 删除订阅相关
            user_subs = session.exec(select(Subscription).where(Subscription.user_id == user_id)).all()
            for sub in user_subs:
                for target in session.exec(select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)).all():
                    session.delete(target)
                for option in session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)).all():
                    session.delete(option)
                session.delete(sub)
            
            # 删除认证方式
            for auth in session.exec(select(UserAuthMethod).where(UserAuthMethod.user_id == user_id)).all():
                session.delete(auth)
            
            # 删除用户
            session.delete(user)
            deleted_count += 1
        
        session.commit()
        
        # 重置 ID 计数器
        User.set_id_counter(2)
        
    print(f"✅ 清理完成，删除了 {deleted_count} 个用户")
    return deleted_count

def import_legacy_users():
    """导入历史用户"""
    print(f"\n📥 步骤 3: 导入历史用户...")
    
    if not Path(LEGACY_JSON).exists():
        raise FileNotFoundError(f"历史数据文件不存在: {LEGACY_JSON}")
    
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
        'skipped_inactive': 0,
        'skipped_existing': 0
    }
    
    with session_scope() as session:
        # 初始化 ID 计数器
        existing_users = session.exec(select(User)).all()
        if existing_users:
            max_id = max(int(u.user_id) for u in existing_users)
            User.set_id_counter(max_id)
            print(f"   ID 计数器: 从 {max_id + 1:06d} 开始")
        
        for qq_id, user_info in users_data.items():
            if not user_info.get('activate', False):
                stats['skipped_inactive'] += 1
                continue
            
            # 检查是否已存在
            existing_auth = session.exec(
                select(UserAuthMethod).where(
                    UserAuthMethod.provider_user_id == str(qq_id),
                    UserAuthMethod.provider == "qq"
                )
            ).first()
            
            if existing_auth:
                stats['skipped_existing'] += 1
                continue
            
            # 创建新用户
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
            
            # 创建认证绑定
            auth_method = UserAuthMethod(
                user_id=new_user_id,
                provider_user_id=str(qq_id),
                provider="qq",
                is_primary=True
            )
            session.add(auth_method)
            stats['auth_methods_created'] += 1
            
            # 创建订阅
            sub = Subscription(user_id=new_user_id)
            session.add(sub)
            session.flush()
            stats['subs_created'] += 1
            
            # 创建订阅选项
            option = SubscriptionOption(
                subscription_id=sub.id,
                notification_level=attention_mode
            )
            session.add(option)
            
            # 导入剧目订阅
            subscribe_data = user_info.get('subscribe', {})
            added_targets = set()  # 用于去重
            
            for event in subscribe_data.get('subscribe_events', []):
                event_id = event.get('id')
                if event_id:
                    target_key = (sub.id, 'EVENT', str(event_id))
                    if target_key not in added_targets:
                        # 再次检查数据库中是否已存在
                        existing_target = session.exec(
                            select(SubscriptionTarget).where(
                                SubscriptionTarget.subscription_id == sub.id,
                                SubscriptionTarget.kind == "EVENT",
                                SubscriptionTarget.target_id == str(event_id)
                            )
                        ).first()
                        
                        if not existing_target:
                            # 查找正确名称
                            event_name_in_db = None
                            try:
                                hq_event = session.get(HulaquanEvent, str(event_id))
                                if hq_event:
                                    event_name_in_db = hq_event.title
                            except Exception:
                                pass

                            target = SubscriptionTarget(
                                subscription_id=sub.id,
                                kind="EVENT",
                                target_id=str(event_id),
                                name=event_name_in_db  # 使用数据库中的真实名称
                            )
                            session.add(target)
                            stats['events_added'] += 1
                            added_targets.add(target_key)
            
            # 导入演员订阅
            for actor_data in subscribe_data.get('subscribe_actors', []):
                actor_name = actor_data.get('actor')
                if actor_name:
                    target_key = (sub.id, 'ACTOR', actor_name)
                    if target_key not in added_targets:
                        # 再次检查数据库中是否已存在
                        existing_target = session.exec(
                            select(SubscriptionTarget).where(
                                SubscriptionTarget.subscription_id == sub.id,
                                SubscriptionTarget.kind == "ACTOR",
                                SubscriptionTarget.target_id == actor_name
                            )
                        ).first()
                        
                        if not existing_target:
                            include_events = [str(e) for e in actor_data.get('include_events', [])]
                            target = SubscriptionTarget(
                                subscription_id=sub.id,
                                kind="ACTOR",
                                target_id=actor_name,
                                name=actor_name,
                                include_plays=include_events if include_events else None
                            )
                            session.add(target)
                            stats['actors_added'] += 1
                            added_targets.add(target_key)
        
        session.commit()
    
    print(f"✅ 导入完成:")
    print(f"   - 创建用户: {stats['users_created']}")
    print(f"   - 创建认证绑定: {stats['auth_methods_created']}")
    print(f"   - 导入剧目: {stats['events_added']}")
    print(f"   - 导入演员: {stats['actors_added']}")
    print(f"   - 跳过未激活: {stats['skipped_inactive']}")
    print(f"   - 跳过已存在: {stats['skipped_existing']}")
    
    return stats['users_created']

def verify_migration():
    """验证迁移结果"""
    print("\n🔍 步骤 4: 验证迁移结果...")
    
    with session_scope() as session:
        total_users = len(session.exec(select(User)).all())
        
        # 验证核心用户
        preserved_ok = all(session.get(User, uid) for uid in PRESERVED_USER_IDS)
        
        # 验证新用户 ID 格式
        all_users = session.exec(select(User)).all()
        invalid_ids = []
        for u in all_users:
            if not u.user_id.isdigit() or len(u.user_id) != 6:
                invalid_ids.append(u.user_id)
        
        print(f"   总用户数: {total_users}")
        print(f"   核心用户: {'✅ 完好' if preserved_ok else '❌ 缺失'}")
        print(f"   ID 格式: {'✅ 全部正确' if not invalid_ids else f'❌ 发现异常: {invalid_ids}'}")
        
        return len(invalid_ids) == 0 and preserved_ok

def main():
    """主函数"""
    force = '--force' in sys.argv
    
    print("=" * 60)
    print("🚀 云端用户数据一键迁移脚本")
    print("=" * 60)
    
    # 安全确认
    if not force:
        print("\n⚠️  警告：此操作将：")
        print("  1. 备份当前数据库")
        print("  2. 保留 000001 和 000002 用户")
        print("  3. 删除其他所有用户")
        print("  4. 重新导入历史用户（6位ID格式）")
        print()
        response = input("确认继续？(输入 'YES' 继续): ")
        if response != "YES":
            print("❌ 操作已取消")
            return
    
    report = MigrationReport()
    
    try:
        # 1. 备份
        report.backup_path = backup_database()
        
        # 2. 获取保留用户信息
        report.preserved_users = get_preserved_users_info()
        
        # 3. 清理
        report.deleted_count = cleanup_users()
        
        # 4. 导入
        report.imported_count = import_legacy_users()
        
        # 5. 验证
        if not verify_migration():
            report.errors.append("数据验证失败，请检查日志")
        
    except Exception as e:
        report.errors.append(f"迁移过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 打印报告
        report.print_summary()
    
    if report.errors:
        print(f"\n⚠️  迁移过程中出现错误，可从备份恢复: {report.backup_path}")
        sys.exit(1)
    else:
        print(f"\n✅ 迁移成功！备份文件已保存: {report.backup_path}")
        sys.exit(0)

if __name__ == "__main__":
    main()
