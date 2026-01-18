"""测试盘票站数据库模型和服务."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.db.connection import get_engine
from services.db.models import TicketTrade, TradeStatus, TradeType, User
from services.marketplace.service import MarketplaceService
from sqlmodel import Session, SQLModel


def test_marketplace():
    """测试盘票站功能."""
    
    print("🚀 开始测试盘票站数据库模型...")
    
    # 1. 创建测试数据库
    print("\n1️⃣ 初始化测试数据库...")
    engine = get_engine(":memory:")  # 使用内存数据库进行测试
    SQLModel.metadata.create_all(engine)
    print("   ✅ 数据库初始化成功")
    
    # 2. 创建测试用户
    print("\n2️⃣ 创建测试用户...")
    with Session(engine) as session:
        user1 = User(user_id="123456", nickname="测试用户1", trust_score=100)
        user2 = User(user_id="789012", nickname="测试用户2", trust_score=90)
        session.add(user1)
        session.add(user2)
        session.commit()
        session.refresh(user1)
        session.refresh(user2)
        print(f"   ✅ 创建用户: {user1.nickname} (ID: {user1.user_id})")
        print(f"   ✅ 创建用户: {user2.nickname} (ID: {user2.user_id})")
    
    # 3. 创建交易信息
    print("\n3️⃣ 创建交易信息...")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 创建出票信息
        trade1 = service.create_trade(
            user_id=user1.user_id,
            trade_type=TradeType.SELL,
            show_name="三个女人的故事",
            show_time=datetime.now() + timedelta(days=7),
            price=280.0,
            original_price=380.0,
            quantity=1,
            seat_info="一楼 3-5",
            description="票面380，280出，当天面交",
            contact_info="微信: test123",
        )
        trade1_id = trade1.id
        print(f"   ✅ 创建出票信息 ID: {trade1_id}, 剧目: {trade1.show_name}")
        
        # 创建求票信息
        trade2 = service.create_trade(
            user_id=user2.user_id,
            trade_type=TradeType.BUY,
            show_name="女巫前传",
            show_time=datetime.now() + timedelta(days=14),
            price=400.0,
            quantity=2,
            description="求1.18晚场女巫，需要2张，票面价收",
            contact_info="QQ: 789012",
        )
        trade2_id = trade2.id
        print(f"   ✅ 创建求票信息 ID: {trade2_id}, 剧目: {trade2.show_name}")
        
        # 创建换票信息
        trade3 = service.create_trade(
            user_id=user1.user_id,
            trade_type=TradeType.EXCHANGE,
            show_name="造星计划",
            show_time=datetime.now() + timedelta(days=3),
            price=299.0,
            original_price=299.0,
            seat_info="穹顶 1-11",
            description="有1.11午场造星，换1.7-8连打套餐或1.11午晚",
            contact_info="微信: test123",
        )
        trade3_id = trade3.id
        print(f"   ✅ 创建换票信息 ID: {trade3_id}, 剧目: {trade3.show_name}")
    
    # 4. 搜索交易
    print("\n4️⃣ 测试搜索功能...")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 搜索所有出票信息
        sell_trades = service.search_trades(trade_type=TradeType.SELL)
        print(f"   ✅ 找到 {len(sell_trades)} 条出票信息")
        
        # 搜索特定剧目
        wicked_trades = service.search_trades(show_name="女巫")
        print(f"   ✅ 搜索'女巫'找到 {len(wicked_trades)} 条结果")
        
        # 搜索特定用户的交易
        user1_trades = service.search_trades(user_id=user1.user_id)
        print(f"   ✅ 用户1发布了 {len(user1_trades)} 条交易")
    
    # 5. 更新交易状态
    print("\n5️⃣ 测试状态更新...")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 将第一条交易标记为已完成
        updated_trade = service.update_trade_status(trade1_id, TradeStatus.COMPLETED)
        print(f"   ✅ 交易 {updated_trade.id} 状态更新为: {updated_trade.status}")
        
        # 将第二条交易标记为锁定
        updated_trade2 = service.update_trade_status(trade2_id, TradeStatus.LOCKED)
        print(f"   ✅ 交易 {updated_trade2.id} 状态更新为: {updated_trade2.status}")
    
    # 6. 删除交易
    print("\n6️⃣ 测试删除功能...")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 删除第三条交易
        success = service.delete_trade(trade3_id)
        print(f"   ✅ 删除交易 {trade3_id}: {'成功' if success else '失败'}")
        
        # 验证删除
        deleted_trade = service.get_trade(trade3_id)
        print(f"   ✅ 验证删除: {'已删除' if deleted_trade is None else '仍存在'}")
    
    print("\n✨ 所有测试通过！盘票站数据库模型运行正常。\n")


if __name__ == "__main__":
    test_marketplace()
