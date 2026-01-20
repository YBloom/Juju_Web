#!/usr/bin/env python3
"""数据库迁移脚本：为 TicketCastAssociation 表添加 rank 字段

使用方法：
    python3.12 scripts/migrate_001_add_cast_rank.py
"""

import sqlite3
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.db.connection import DEFAULT_DB_PATH


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """检查表中是否存在指定列"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(col[1] == column_name for col in columns)


def main():
    db_path = DEFAULT_DB_PATH
    print(f"数据库路径: {db_path}")
    
    if not db_path.exists():
        print(f"错误：数据库文件不存在 {db_path}")
        return 1
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # 检查 rank 列是否已存在
        if check_column_exists(cursor, "ticketcastassociation", "rank"):
            print("✓ rank 字段已存在，无需迁移")
            return 0
        
        # 添加 rank 列
        print("正在添加 rank 字段...")
        cursor.execute("""
            ALTER TABLE ticketcastassociation 
            ADD COLUMN rank INTEGER DEFAULT 999
        """)
        conn.commit()
        
        print("✓ 成功添加 rank 字段（默认值：999）")
        
        # 验证
        if check_column_exists(cursor, "ticketcastassociation", "rank"):
            print("✓ 迁移验证通过")
            return 0
        else:
            print("✗ 迁移验证失败")
            return 1
            
    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
