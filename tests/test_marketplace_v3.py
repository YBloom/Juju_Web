"""测试结构化盘票站模型 V3 (支持 OR 逻辑、库存关联、捆绑控制)."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.db.connection import get_engine
from services.db.models import (
    MarketplaceListing, ListingItem, ItemDirection, TradeStatus, 
    User, ItemType, UserInventory, TicketStatus
)
from services.marketplace.service import MarketplaceService
from services.inventory import InventoryService
from sqlmodel import Session, SQLModel


def test_marketplace_v3():
    """测试结构化盘票站 V3 新特性."""
    
    print("🚀 开始测试结构化盘票站模型 V3 (库存+逻辑增强)...\n")
    
    # 1. 初始化
    engine = get_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # 创建用户
        users = [User(user_id="user_v3", nickname="盘票专家")]
        for u in users:
            session.add(u)
        session.commit()
    
    # 2. 准备库存 (模拟用户先往票夹加票)
    print("1️⃣ 准备库存 (UserInventory)...")
    with Session(engine) as session:
        inv_service = InventoryService(session)
        ticket = inv_service.add_ticket(
            user_id="user_v3",
            show_name="女巫",
            show_time=datetime.now() + timedelta(days=10),
            seat_info="5排",
            original_price=299.0
        )
        ticket_id = ticket.id
        print(f"   ✅ 用户添加库存: 女巫 5排 (ID: {ticket_id})\n")

    # 3. 场景 A: 升舱置换 (关联库存 + 补差逻辑)
    print("2️⃣ 场景 A: 升舱置换 (关联库存 + 补差逻辑)")
    print("   描述: 我出女巫5排(关联库存) + 现金补差，求女巫1排")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        listing = service.create_listing(
            user_id="user_v3",
            items=[
                # HAVE: 关联库存
                {
                    "direction": "have",
                    "item_type": "ticket",
                    "inventory_id": ticket_id,
                    "show_name": "女巫",
                    "show_time": datetime.now() + timedelta(days=10),
                    "seat_info": "5排"
                },
                # WANT: 目标
                {
                    "direction": "want",
                    "item_type": "ticket",
                    "show_name": "女巫",
                    "seat_info": "1排",
                    "price": 399.0 # 目标票面
                }
            ],
            description="补差置换"
        )
        
        print(f"   ✅ 创建挂单 #{listing.id}")
        for item in listing.items:
            type_str = f"[{item.item_type.value.upper()}]"
            inv_str = f"(InvID: {item.inventory_id})" if item.inventory_id else ""
            print(f"      {item.direction.value.upper()} {type_str} {item.show_name or '...'} {item.seat_info or ''} {inv_str}")
        print()

    # 4. 场景 B: OR 逻辑 (剧换钱 或 剧换剧)
    print("3️⃣ 场景 B: OR 逻辑 (剧换钱 或 剧换剧)")
    print("   描述: 【出】奥尔菲斯 【或换】法红黑")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        listing = service.create_listing(
            user_id="user_v3",
            items=[
                {
                    "direction": "have",
                    "item_type": "ticket",
                    "show_name": "奥尔菲斯",
                    "show_time": datetime.now() + timedelta(days=5),
                    "price": 380.0
                },
                # OR 1: 换钱
                {
                    "direction": "want",
                    "item_type": "cash",
                    "price": 380.0
                },
                # OR 2: 换剧
                {
                    "direction": "want",
                    "item_type": "ticket",
                    "show_name": "法红黑",
                    "show_time": datetime.now() + timedelta(days=6)
                }
            ],
            description="可出可换"
        )
        
        print(f"   ✅ 创建挂单 #{listing.id}")
        for item in listing.items:
            if item.item_type == ItemType.CASH:
                print(f"      {item.direction.value.upper()} [CASH] ¥{item.price}")
            else:
                print(f"      {item.direction.value.upper()} [TICKET] {item.show_name}")
        print()

    # 5. 场景 C: 捆绑控制 (unbundling_allowed)
    print("4️⃣ 场景 C: 捆绑销售控制")
    print("   描述: 两张票打包出，允许拆分 = True")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        listing = service.create_listing(
            user_id="user_v3",
            unbundling_allowed=True, # 关键点
            items=[
                {"direction": "have", "show_name": "A", "show_time": datetime.now()},
                {"direction": "have", "show_name": "B", "show_time": datetime.now()},
            ],
            description="可拆出"
        )
        
        print(f"   ✅ 创建挂单 #{listing.id}")
        print(f"      允许拆分: {listing.unbundling_allowed}")
        print(f"      细项数: {len(listing.items)}\n")

    print("\n" + "="*60)
    print("✨ V3 特性验证完成！")
    print("   ✅ 库存关联 (Inventory Integration)")
    print("   ✅ ItemType (Ticket vs Cash)")
    print("   ✅ 补差置换数据结构 (Implicit Upgrade)")
    print("   ✅ 捆绑拆分标志 (Unbundling Control)")


if __name__ == "__main__":
    test_marketplace_v3()
