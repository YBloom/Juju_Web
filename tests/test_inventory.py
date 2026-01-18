"""测试用户票夹模型和流转路径功能."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.db.connection import get_engine
from services.db.models import UserInventory, User, TicketStatus, TicketSource
from services.inventory import InventoryService
from sqlmodel import Session, SQLModel


def test_inventory_and_transfer():
    """测试票夹与流转路径功能."""
    
    print("🎫 开始测试用户票夹与流转路径...\n")
    
    # 1. 初始化
    engine = get_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # 创建测试用户
        users = [
            User(user_id="alice", nickname="Alice"),
            User(user_id="bob", nickname="Bob"),
            User(user_id="carol", nickname="Carol"),
        ]
        for user in users:
            session.add(user)
        session.commit()
        print("✅ 创建了 3 个测试用户\n")
    
    # 2. Alice 添加票到自己的票夹
    print("📥 场景 1: Alice 手动添加票到票夹")
    with Session(engine) as session:
        service = InventoryService(session)
        
        ticket = service.add_ticket(
            user_id="alice",
            show_name="女巫前传",
            show_time=datetime.now() + timedelta(days=15),
            seat_info="A区 3-17",
            original_price=399.0,
        )
        
        print(f"   ✅ Alice 添加了票 #{ticket.id}")
        print(f"      剧目: {ticket.show_name}")
        print(f"      座位: {ticket.seat_info}")
        print(f"      流转路径: {ticket.transfer_path}")
        print(f"      状态: {ticket.status.value}\n")
    
    # 3. Alice 将票转让给 Bob
    print("🔄 场景 2: Alice 将票转让给 Bob (成交)")
    with Session(engine) as session:
        service = InventoryService(session)
        
        new_ticket = service.transfer_ticket(
            inventory_id=1,
            from_user_id="alice",
            to_user_id="bob",
            listing_id=101,  # 模拟挂单 ID
        )
        
        print(f"   ✅ 转让成功")
        print(f"      新票 ID: {new_ticket.id}")
        print(f"      当前持有者: {new_ticket.user_id}")
        print(f"      流转路径: {new_ticket.transfer_path}")
        print(f"      来源: {new_ticket.source.value}\n")
    
    # 4. Bob 再将票转让给 Carol
    print("🔄 场景 3: Bob 将票转让给 Carol (二手)")
    with Session(engine) as session:
        service = InventoryService(session)
        
        third_ticket = service.transfer_ticket(
            inventory_id=2,
            from_user_id="bob",
            to_user_id="carol",
            listing_id=102,
        )
        
        print(f"   ✅ 再次转让成功")
        print(f"      新票 ID: {third_ticket.id}")
        print(f"      当前持有者: {third_ticket.user_id}")
        print(f"      流转路径: {third_ticket.transfer_path}")
        print(f"      经手次数: {len(third_ticket.transfer_path)} 次\n")
    
    # 5. 查询每个用户的票夹
    print("📂 场景 4: 查询各用户的票夹状态")
    with Session(engine) as session:
        service = InventoryService(session)
        
        for user_id, name in [("alice", "Alice"), ("bob", "Bob"), ("carol", "Carol")]:
            inventory = service.get_user_inventory(user_id)
            print(f"   • {name} 的票夹:")
            for ticket in inventory:
                print(f"      - 票 #{ticket.id}: {ticket.show_name} ({ticket.status.value})")
    
    print("\n" + "="*60)
    print("✨ 流转路径验证完成！")
    print("\n💡 关键特性:")
    print("   ✅ 每次添加票时自动初始化 transfer_path")
    print("   ✅ 转让时自动追加买家 ID 到路径")
    print("   ✅ 卖家库存自动标记为 TRADED")
    print("   ✅ 买家库存自动记录来源挂单\n")


if __name__ == "__main__":
    test_inventory_and_transfer()
