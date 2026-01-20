#!/usr/bin/env python3
"""
历史用户订阅数据导入脚本
从 UsersManager.json 导入旧系统的订阅数据到新系统
"""
import sqlite3
import json
import sys
from datetime import datetime
from pathlib import Path

# 数据文件路径
LEGACY_JSON = "plugins_legacy/data_legacy_260118_final/data/data_manager/UsersManager.json"
DB_PATH = "data/musicalbot.db"

def get_now():
    """获取当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def map_attention_mode(attention_str):
    """
    映射 attention_to_hulaquan 到 notification_level
    旧系统: "1"=上新, "2"=上新+补票+回流, "3"=全量
    新系统: 0=关闭, 1=上新, 2=上新+补票, 3=上新+补票+回流, 4=+票减, 5=全量
    
    映射规则：
    - 旧"0" → 新0 (关闭)
    - 旧"1" → 新2 (上新+补票，旧系统的"上新"在新系统中对应"上新+补票")
    - 旧"2" → 新3 (上新+补票+回流)
    - 旧"3" → 新5 (全量)
    """
    if isinstance(attention_str, str):
        val = int(attention_str)
    else:
        val = int(attention_str) if attention_str is not None else 0
    
    # 映射规则
    mapping = {0: 0, 1: 2, 2: 3, 3: 5}
    return mapping.get(val, 0)

def import_users(db_path=DB_PATH, json_path=LEGACY_JSON):
    """导入历史用户数据"""
    # 1. 读取JSON
    print(f"📖 正在读取历史数据: {json_path}")
    if not Path(json_path).exists():
        print(f"❌ 文件不存在: {json_path}")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    users_data = data.get('users', {})
    print(f"   发现 {len(users_data)} 个历史用户")
    
    # 2. 连接数据库
    print(f"\n🔗 正在连接数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {
        'users_created': 0,
        'subs_created': 0,
        'global_level_set': 0,
        'events_added': 0,
        'actors_added': 0,
        'tickets_skipped': 0
    }
    
    try:
        print("\n🚀 开始导入数据...")
        
        # 检查user表结构
        cursor.execute("PRAGMA table_info(user)")
        user_cols = [c[1] for c in cursor.fetchall()]
        has_global_level = 'global_notification_level' in user_cols
        
        for user_id, user_info in users_data.items():
            # 检查用户激活状态
            if not user_info.get('activate', False):
                continue
            
            # 1. 确保User记录存在
            cursor.execute("SELECT 1 FROM user WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                now = get_now()
                attention_mode = map_attention_mode(user_info.get('attention_to_hulaquan', 0))
                
                if has_global_level:
                    # 新本地结构：包含global_notification_level
                    cursor.execute("""
                        INSERT INTO user (
                            user_id, is_deleted, created_at, updated_at, active, 
                            transactions_success, trust_score, bot_interaction_mode,
                            global_notification_level
                        ) VALUES (?, 0, ?, ?, 1, 0, 100, 'hybrid', ?)
                    """, (user_id, now, now, attention_mode))
                else:
                    # 旧云端结构：不含global_notification_level
                    cursor.execute("""
                        INSERT INTO user (
                            user_id, is_deleted, created_at, updated_at, active, 
                            transactions_success, trust_score, bot_interaction_mode
                        ) VALUES (?, 0, ?, ?, 1, 0, 100, 'hybrid')
                    """, (user_id, now, now))
                stats['users_created'] += 1
            
            # 2. 获取全局通知级别
            attention_mode = map_attention_mode(user_info.get('attention_to_hulaquan', 0))
            
            # 3. 确保Subscription记录存在
            cursor.execute("SELECT id FROM subscription WHERE user_id = ?", (user_id,))
            sub_row = cursor.fetchone()
            
            if sub_row:
                sub_id = sub_row[0]
            else:
                now = get_now()
                cursor.execute("""
                    INSERT INTO subscription (user_id, created_at, updated_at) 
                    VALUES (?, ?, ?)
                """, (user_id, now, now))
                sub_id = cursor.lastrowid
                stats['subs_created'] += 1
            
            # 4. 设置全局通知级别（SubscriptionOption）
            if attention_mode > 0:
                cursor.execute("SELECT id FROM subscriptionoption WHERE subscription_id = ?", (sub_id,))
                if not cursor.fetchone():
                    now = get_now()
                    cursor.execute("""
                        INSERT INTO subscriptionoption (
                            subscription_id, notification_level, mute, freq, allow_broadcast, 
                            created_at, updated_at
                        ) VALUES (?, ?, 0, 'REALTIME', 1, ?, ?)
                    """, (sub_id, attention_mode, now, now))
                    stats['global_level_set'] += 1
            
            # 5. 导入剧目订阅 (subscribe_events)
            subscribe_obj = user_info.get('subscribe', {})
            events = subscribe_obj.get('subscribe_events', [])
            
            for event in events:
                event_id = event.get('id')
                mode = event.get('mode', 2)
                
                # 检查是否已存在
                cursor.execute("""
                    SELECT id FROM subscriptiontarget 
                    WHERE subscription_id = ? AND kind = 'PLAY' AND target_id = ?
                """, (sub_id, event_id))
                
                if not cursor.fetchone():
                    now = get_now()
                    cursor.execute("""
                        INSERT INTO subscriptiontarget (
                            subscription_id, kind, target_id, created_at, updated_at
                        ) VALUES (?, 'PLAY', ?, ?, ?)
                    """, (sub_id, event_id, now, now))
                    stats['events_added'] += 1
            
            # 6. 导入演员订阅 (subscribe_actors)
            actors = subscribe_obj.get('subscribe_actors', [])
            
            for actor in actors:
                actor_name = actor.get('actor')
                mode = actor.get('mode', 2)
                include_events = actor.get('include_events', [])
                
                # 检查是否已存在
                cursor.execute("""
                    SELECT id FROM subscriptiontarget 
                    WHERE subscription_id = ? AND kind = 'ACTOR' AND target_id = ?
                """, (sub_id, actor_name))
                
                if not cursor.fetchone():
                    now = get_now()
                    # 将include_events转为JSON存储在include_plays字段
                    include_plays = json.dumps(include_events) if include_events else None
                    cursor.execute("""
                        INSERT INTO subscriptiontarget (
                            subscription_id, kind, target_id, name, include_plays, created_at, updated_at
                        ) VALUES (?, 'ACTOR', ?, ?, ?, ?, ?)
                    """, (sub_id, actor_name, actor_name, include_plays, now, now))
                    stats['actors_added'] += 1
            
            # 7. 跳过 subscribe_tickets（不再适用）
            tickets = subscribe_obj.get('subscribe_tickets', [])
            stats['tickets_skipped'] += len(tickets)
        
        # 提交
        conn.commit()
        print("\n✨ 导入完成！")
        
        # 显示统计
        print("\n📊 导入统计:")
        print(f"   - 创建用户: {stats['users_created']}")
        print(f"   - 创建订阅: {stats['subs_created']}")
        print(f"   - 设置全局级别: {stats['global_level_set']}")
        print(f"   - 导入剧目订阅: {stats['events_added']}")
        print(f"   - 导入演员订阅: {stats['actors_added']}")
        print(f"   - 跳过票务订阅: {stats['tickets_skipped']}")
        
    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    # 支持命令行参数
    db = DB_PATH
    json_file = LEGACY_JSON
    
    if len(sys.argv) > 1:
        db = sys.argv[1]
    if len(sys.argv) > 2:
        json_file = sys.argv[2]
    
    print("=" * 60)
    print("历史用户订阅数据导入工具")
    print("=" * 60)
    import_users(db, json_file)
    print("=" * 60)
