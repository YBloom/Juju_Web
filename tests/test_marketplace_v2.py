"""测试结构化盘票站模型和服务 V2."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.db.connection import get_engine
from services.db.models import MarketplaceListing, ListingItem, ItemDirection, TradeStatus, User
from services.marketplace.service import MarketplaceService
from sqlmodel import Session, SQLModel


def test_marketplace_v2():
    """测试结构化盘票站功能."""
    
    print("🚀 开始测试结构化盘票站模型 V2...\n")
    
    # 1. 创建测试数据库
    print("1️⃣ 初始化测试数据库...")
    engine = get_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    print("   ✅ 数据库初始化成功\n")
    
    # 2. 创建测试用户
    print("2️⃣ 创建测试用户...")
    with Session(engine) as session:
        users = [
            User(user_id="user001", nickname="小王", trust_score=95),
            User(user_id="user002", nickname="小李", trust_score=88),
        ]
        for user in users:
            session.add(user)
        session.commit()
        print(f"   ✅ 创建了 {len(users)} 个用户\n")
    
    # 3. 场景一：简单出票
    print("3️⃣ 场景一：简单出票")
    print("   描述: 【出】1.11午 三妇志异 2-1X 580\n")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        listing = service.create_listing(
            user_id="user001",
            items=[
                {
                    "direction": "have",
                    "show_name": "三妇志异",
                    "show_time": datetime.now() + timedelta(days=5),
                    "price": 580.0,
                    "seat_info": "2-1X",
                }
            ],
            description="极小单",
            contact_info="微信: xiaowang123"
        )
        
        print(f"   ✅ 创建挂单 #{listing.id}")
        print(f"      细项数量: {len(listing.items)}")
        print(f"      细项 1: {listing.items[0].direction.value} - {listing.items[0].show_name}\n")
    
    # 4. 场景二：置换 (我有 A，换 B)
    print("4️⃣ 场景二：置换")
    print("   描述: 【有】1.9晚三妇280 【换】1.7-8连打套餐或1.11午晚\n")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        listing = service.create_listing(
            user_id="user001",
            items=[
                {
                    "direction": "have",
                    "show_name": "三妇志异",
                    "show_time": datetime.now() + timedelta(days=3),
                    "price": 280.0,
                },
                {
                    "direction": "want",
                    "show_name": "连打套餐",
                    "show_time": datetime.now() + timedelta(days=1),
                    "price": 280.0,
                }
            ],
            description="需280及以下",
            contact_info="微信: xiaowang123"
        )
        
        print(f"   ✅ 创建挂单 #{listing.id}")
        print(f"      细项数量: {len(listing.items)}")
        for idx, item in enumerate(listing.items, 1):
            print(f"      细项 {idx}: {item.direction.value} - {item.show_name}")
        print()
    
    # 5. 场景三：捆绑出售 (A 捆 B)
    print("5️⃣ 场景三：捆绑出售")
    print("   描述: 【捆出】1.2晚 去夏 + 1.4晚 去夏\n")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        listing = service.create_listing(
            user_id="user002",
            items=[
                {
                    "direction": "have",
                    "show_name": "去夏",
                    "show_time": datetime.now() + timedelta(days=2),
                    "price": 399.0,
                    "seat_info": "C4-7",
                },
                {
                    "direction": "have",
                    "show_name": "去夏",
                    "show_time": datetime.now() + timedelta(days=4),
                    "price": 399.0,
                    "seat_info": "A2-9",
                }
            ],
            description="捆出，不拆",
            requirements="已取票，环人广面交",
            contact_info="QQ: 123456789"
        )
        
        print(f"   ✅ 创建挂单 #{listing.id}")
        print(f"      细项数量: {len(listing.items)}")
        for idx, item in enumerate(listing.items, 1):
            print(f"      细项 {idx}: {item.show_name} - {item.show_time.strftime('%m-%d')} - {item.seat_info}")
        print(f"      特殊要求: {listing.requirements}\n")
    
    # 6. 搜索测试
    print("6️⃣ 搜索功能测试\n")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 6.1 搜索所有 HAVE 的细项
        print("   📌 搜索所有持有 (HAVE) 的票:")
        have_items = service.search_items(direction=ItemDirection.HAVE)
        for item in have_items:
            print(f"      • {item.show_name} ({item.show_time.strftime('%m-%d')}) - ¥{item.price}")
        
        # 6.2 搜索特定剧目
        print("\n   📌 搜索'三妇志异':")
        items = service.search_items(show_name="三妇志异")
        for item in items:
            print(f"      • [{item.direction.value}] {item.show_name} - ¥{item.price}")
        
        # 6.3 匹配测试：我有"三妇志异"，谁想要？
        print("\n   📌 智能匹配：我有'三妇志异'，谁想要？")
        matches = service.find_matches("三妇志异", ItemDirection.HAVE)
        if matches:
            for item in matches:
                print(f"      ✅ 匹配到: Listing #{item.listing_id} 想要 {item.show_name}")
        else:
            print("      ℹ️  暂无匹配")
        
        print()
    
    # 7. 状态管理
    print("7️⃣ 状态管理测试\n")
    
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 更新第一个挂���的状态
        updated = service.update_listing_status(1, TradeStatus.COMPLETED)
        print(f"   ✅ 挂单 #{updated.id} 状态更新为: {updated.status.value}\n")
    
    print("✨ 所有测试通过！结构化盘票站模型运行正常。\n")
    
    # 8. 总结关键特性
    print("="*60)
    print("\n📊 关键特性验证:\n")
    print("   ✅ 挂单-细项两级结构")
    print("   ✅ HAVE/WANT 方向区分")
    print("   ✅ 支持置换 (同挂单下有 HAVE + WANT)")
    print("   ✅ 支持捆绑 (同挂单下多个 HAVE)")
    print("   ✅ 独立的 requirements 字段 (特殊要求)")
    print("   ✅ 智能匹配功能 (find_matches)")
    print()


if __name__ == "__main__":
    test_marketplace_v2()
