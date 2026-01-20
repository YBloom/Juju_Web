#!/usr/bin/env python3
"""回填历史卡司数据的 rank 字段

遍历所有 TicketCastAssociation 记录，根据 Saoju 的 role_orders 数据
为每条记录填充正确的 rank 值。

使用方法：
    python3.12 scripts/backfill_cast_ranks.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.db.connection import session_scope
from services.hulaquan.tables import TicketCastAssociation, HulaquanEvent, HulaquanTicket
from services.saoju.service import SaojuService
from sqlmodel import select


async def backfill_ranks():
    """回填所有卡司关联的 rank 值"""
    
    # 初始化 SaojuService 并确保索引加载
    saoju = SaojuService()
    print("正在加载 Saoju 索引数据...")
    await saoju._ensure_artist_indexes()
    
    role_orders_cache = saoju.data.get("artist_indexes", {}).get("role_orders", {})
    print(f"已加载 {len(role_orders_cache)} 个剧目的角色顺序数据")
    
    # 统计信息
    total_records = 0
    updated_records = 0
    no_musical_id = 0
    no_role_order = 0
    
    with session_scope() as session:
        # 获取所有卡司关联记录
        stmt = select(TicketCastAssociation)
        associations = session.exec(stmt).all()
        total_records = len(associations)
        
        print(f"\n开始处理 {total_records} 条卡司关联记录...")
        
        for i, assoc in enumerate(associations, 1):
            if i % 100 == 0:
                print(f"  进度: {i}/{total_records}")
            
            # 如果已经有正确的 rank（不是默认值），跳过
            if assoc.rank != 999:
                continue
            
            # 没有角色信息，无法排序
            if not assoc.role:
                continue
            
            # 获取对应的 ticket 和 event
            ticket = session.get(HulaquanTicket, assoc.ticket_id)
            if not ticket:
                continue
            
            event = session.get(HulaquanEvent, ticket.event_id)
            if not event or not event.saoju_musical_id:
                no_musical_id += 1
                continue
            
            # 获取这个剧目的角色顺序
            role_orders = role_orders_cache.get(str(event.saoju_musical_id), {})
            if not role_orders:
                no_role_order += 1
                continue
            
            # 获取这个角色的 rank
            new_rank = role_orders.get(assoc.role)
            if new_rank is not None and new_rank != assoc.rank:
                assoc.rank = new_rank
                session.add(assoc)
                updated_records += 1
        
        # 提交所有更新
        print(f"\n正在保存更新...")
        session.commit()
    
    # 输出统计
    print(f"\n✓ 回填完成！")
    print(f"  总记录数: {total_records}")
    print(f"  已更新: {updated_records}")
    print(f"  未关联剧目ID: {no_musical_id}")
    print(f"  缺少角色顺序数据: {no_role_order}")
    print(f"  未变更: {total_records - updated_records - no_musical_id - no_role_order}")


if __name__ == "__main__":
    asyncio.run(backfill_ranks())
