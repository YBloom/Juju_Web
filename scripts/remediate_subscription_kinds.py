#!/usr/bin/env python3.12
"""
SubscriptionTarget Kind Normalization Script
统一订阅目标的 kind 字段为小写枚举值
"""

import sys
import os

# Ensure we can import from the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, text
from services.db.connection import get_engine

def remediate_kinds():
    engine = get_engine()
    with Session(engine) as session:
        print("开始扫描 SubscriptionTarget.kind 字段数据...")
        
        # 统计所有记录
        raw_results = session.execute(text("SELECT kind, COUNT(*) FROM subscriptiontarget GROUP BY kind")).all()
        
        to_fix = []
        for kind_result, count in raw_results:
            kind_str = str(kind_result) if kind_result else ""
            if kind_str and kind_str != kind_str.upper():
                to_fix.append((kind_str, count))
        
        if not to_fix:
            print("[✓] 没有发现需要修复的异常 (非大写) kind 格式。")
            return
            
        print(f"发现以下需要修复的记录: {to_fix}")
        
        for kind_str, count in to_fix:
            new_kind = kind_str.upper()
            print(f"  - 正在修复: '{kind_str}' -> '{new_kind}' ({count} 条记录)")
            
            # 使用原生 SQL 避免 SQLModel 枚举转换异常
            session.execute(
                text("UPDATE subscriptiontarget SET kind = :new_kind WHERE kind = :old_kind"),
                {"new_kind": new_kind, "old_kind": kind_str}
            )
        
        session.commit()
        print("\n[✓] 数据修复完成！所有 kind 字段已统一为小写。")

if __name__ == "__main__":
    remediate_kinds()
