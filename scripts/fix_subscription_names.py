#!/usr/bin/env python3
"""
修复订阅数据脚本
================
功能：
1. 查找 SubscriptionTarget 表中 kind='EVENT' (PLAY) 且 name 为空的记录
2. 根据 target_id (即 event_id) 查询 HulaquanEvent 表获取正确标题
3. 回填 name 字段

使用方法：
    python3.12 scripts/fix_subscription_names.py
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.db.connection import session_scope
from services.db.models import SubscriptionTarget, HulaquanEvent
from services.db.models.base import SubscriptionTargetKind
from sqlmodel import select, col

def fix_subscription_names():
    print("🚀 开始修复订阅数据...")
    
    updated_count = 0
    failed_count = 0
    
    with session_scope() as session:
        # 1. 查找所有名字为空的剧目订阅
        # 兼容各种历史数据格式: PLAY, play, EVENT, event
        target_kinds = [
            SubscriptionTargetKind.PLAY, 
            "play", "PLAY", 
            "event", "EVENT"
        ]
        
        stmt = select(SubscriptionTarget).where(
            col(SubscriptionTarget.kind).in_(target_kinds),
            (SubscriptionTarget.name == None) | (SubscriptionTarget.name == "")
        )
        targets = session.exec(stmt).all()
        
        print(f"📋 发现 {len(targets)} 条缺少名称的订阅记录")
        
        for target in targets:
            try:
                event_id = target.target_id
                
                # 2. 查询对应的事件信息
                event = session.get(HulaquanEvent, event_id)
                
                if event:
                    target.name = event.title
                    session.add(target)
                    updated_count += 1
                    print(f"   ✅ [修复] ID: {event_id} -> Name: {event.title}")
                else:
                    failed_count += 1
                    print(f"   ⚠️ [警告] ID: {event_id} 在 HulaquanEvent 表中未找到，跳过")
                    
            except Exception as e:
                failed_count += 1
                print(f"   ❌ [错误] 处理 ID {target.target_id} 时出错: {e}")
        
        session.commit()
    
    print("\n" + "=" * 40)
    print(f"修复完成！")
    print(f"✅ 成功更新: {updated_count}")
    print(f"⚠️ 无法修复: {failed_count}")
    print("=" * 40)

if __name__ == "__main__":
    fix_subscription_names()
