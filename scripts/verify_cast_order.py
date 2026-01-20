#!/usr/bin/env python3
"""验证卡司排序修复

测试场景：
1. 查询指定剧目并检查卡司顺序
2. 模拟同步并验证 rank 字段正确保存
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.hulaquan.service import HulaquanService
from services.db.connection import session_scope
from services.hulaquan.tables import TicketCastAssociation, HulaquanCast
from sqlmodel import select


async def verify_cast_order():
    """验证卡司排序功能"""
    
    # 测试查询"她对此感到厌烦"
    search_query = "她对此感到厌烦"
    
    async with HulaquanService() as service:
        print(f"正在搜索: {search_query}")
        events = await service.search_events(search_query)
        
        if not events:
            print(f"未找到匹配的活动")
            return
        
        for event in events:
            print(f"\n活动: {event.title}")
            print(f"  活动ID: {event.id}")
            
            for ticket in event.tickets:
                print(f"\n  场次: {ticket.title}")
                print(f"    时间: {ticket.session_time}")
                
                if ticket.cast:
                    print(f"    卡司顺序 (共{len(ticket.cast)}人):")
                    for i, cast_info in enumerate(ticket.cast, 1):
                        role_str = f" ({cast_info.role})" if cast_info.role else ""
                        print(f"      {i}. {cast_info.name}{role_str}")
                    
                    # 检查数据库中的 rank 值
                    print(f"\n    数据库 rank 验证:")
                    with session_scope() as session:
                        stmt = (
                            select(HulaquanCast.name, TicketCastAssociation.role, TicketCastAssociation.rank)
                            .join(TicketCastAssociation)
                            .where(TicketCastAssociation.ticket_id == ticket.id)
                            .order_by(TicketCastAssociation.rank, HulaquanCast.name)
                        )
                        ranks = session.exec(stmt).all()
                        for name, role, rank in ranks:
                            role_str = f" ({role})" if role else ""
                            print(f"      rank={rank}: {name}{role_str}")
                else:
                    print(f"    卡司: 无")


if __name__ == "__main__":
    asyncio.run(verify_cast_order())
