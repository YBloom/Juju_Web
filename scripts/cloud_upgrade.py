#!/usr/bin/env python3
"""
云端数据库结构升级脚本
用途：仅做表结构调整，不删除任何业务数据
"""
import sqlite3
import sys

DB_PATH = "/opt/MusicalBot/data/musicalbot.db"  # 云端路径

def upgrade(db_path=DB_PATH):
    """执行数据库结构升级"""
    print(f"🔗 正在连接数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Step 1: 检查并添加notification_level列
        print("\n📝 步骤 1/3: 检查并升级表结构...")
        cursor.execute("PRAGMA table_info(subscriptionoption)")
        cols = [c[1] for c in cursor.fetchall()]
        
        if 'notification_level' not in cols:
            print("   添加 notification_level 列...")
            cursor.execute("""
                ALTER TABLE subscriptionoption 
                ADD COLUMN notification_level INTEGER DEFAULT 2 NOT NULL
            """)
            print("   ✅ 列添加成功")
        else:
            print("   ✓ notification_level 列已存在")
        
        # Step 2: 创建性能索引
        print("\n⚡ 步骤 2/3: 创建性能索引...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sub_kind_target 
                ON subscriptiontarget (subscription_id, kind, target_id)
            """)
            print("   ✅ 索引 idx_sub_kind_target 已创建")
        except Exception as e:
            print(f"   ⚠️  索引创建警告: {e}")
        
        # Step 3: 备份并删除旧表
        print("\n🗄️  步骤 3/3: 清理废弃表...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'hulaquansubscription%'")
        old_tables = [r[0] for r in cursor.fetchall()]
        
        for table in old_tables:
            if table == 'hulaquansubscription':
                print(f"   正在备份 {table}...")
                try:
                    cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_backup")
                    print(f"   ✅ {table} 已备份为 {table}_backup")
                except Exception as e:
                    print(f"   ⚠️  备份失败（可能已备份）: {e}")
            elif table.endswith('_backup'):
                print(f"   跳过备份表 {table}")
        
        # 提交所有更改
        conn.commit()
        print("\n✨ 数据库结构升级完成！")
        
        # 显示摘要
        cursor.execute("SELECT COUNT(*) FROM user")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM subscription")
        sub_count = cursor.fetchone()[0]
        
        print("\n📊 当前统计:")
        print(f"   - 用户数: {user_count}")
        print(f"   - 订阅数: {sub_count}")
        print(f"   - 性能索引: 已创建")
        print(f"   - 旧表状态: 已备份")
        
    except Exception as e:
        print(f"\n❌ 升级失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    # 支持命令行参数指定数据库路径
    target = DB_PATH
    if len(sys.argv) > 1:
        target = sys.argv[1]
    
    print("=" * 60)
    print("云端数据库结构升级工具")
    print("=" * 60)
    upgrade(target)
    print("=" * 60)
