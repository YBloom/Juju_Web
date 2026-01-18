"""盘票站完整使用示例 - 包含实际数据操作."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.db.connection import get_engine
from services.db.models import TicketTrade, TradeType, TradeStatus, User
from services.marketplace.service import MarketplaceService
from sqlmodel import Session, SQLModel


def create_sample_data():
    """创建示例数据."""
    
    print("🎭 盘票站完整使用示例\n")
    print("="*60)
    
    # 1. 初始化数据库
    print("\n📦 步骤 1: 初始化数据库...")
    engine = get_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    print("   ✅ 数据库初始化完成\n")
    
    # 2. 创建测试用户
    print("👥 步骤 2: 创建测试用户...")
    with Session(engine) as session:
        users = [
            User(user_id="user001", nickname="剧迷小王", trust_score=95),
            User(user_id="user002", nickname="音乐剧爱好者", trust_score=88),
            User(user_id="user003", nickname="票务达人", trust_score=100),
        ]
        for user in users:
            session.add(user)
        session.commit()
        print(f"   ✅ 创建了 {len(users)} 个用户\n")
    
    # 3. 创建交易信息
    print("🎫 步骤 3: 创建交易信息...")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        trades = [
            # 出票信息
            {
                "user_id": "user001",
                "trade_type": TradeType.SELL,
                "show_name": "三个女人的故事",
                "show_time": datetime.now() + timedelta(days=5),
                "price": 280.0,
                "original_price": 380.0,
                "seat_info": "一楼 3-5",
                "description": "票面380，280出，当天面交",
                "contact_info": "微信: xiaowang123"
            },
            {
                "user_id": "user002",
                "trade_type": TradeType.SELL,
                "show_name": "女巫前传",
                "show_time": datetime.now() + timedelta(days=10),
                "price": 399.0,
                "original_price": 399.0,
                "seat_info": "A区 3-17",
                "description": "DressCode场，票面价出，升舱",
                "contact_info": "QQ: 123456789"
            },
            # 求票信息
            {
                "user_id": "user003",
                "trade_type": TradeType.BUY,
                "show_name": "女巫前传",
                "show_time": datetime.now() + timedelta(days=12),
                "price": 400.0,
                "quantity": 2,
                "description": "求1.18晚场女巫，需要2张，票面价收",
                "contact_info": "微信: daren_piao"
            },
            # 换票信息
            {
                "user_id": "user001",
                "trade_type": TradeType.EXCHANGE,
                "show_name": "造星计划",
                "show_time": datetime.now() + timedelta(days=3),
                "price": 299.0,
                "original_price": 299.0,
                "seat_info": "穹顶 1-11",
                "description": "有1.11午场造星，换1.7-8连打套餐或1.11午晚",
                "contact_info": "微信: xiaowang123"
            },
            {
                "user_id": "user002",
                "trade_type": TradeType.SELL,
                "show_name": "火焰 Flames",
                "show_time": datetime.now() + timedelta(days=8),
                "price": 339.0,
                "original_price": 399.0,
                "seat_info": "B-2-3",
                "description": "小火焰，蔡忻如 田野 许昌泰",
                "contact_info": "QQ: 123456789"
            },
        ]
        
        created_trades = []
        for trade_data in trades:
            trade = service.create_trade(**trade_data)
            created_trades.append(trade)
            type_emoji = {"sell": "💰", "buy": "🔍", "exchange": "🔄"}
            print(f"   {type_emoji[trade.type.value]} 创建{trade.type.value}交易: {trade.show_name} (ID: {trade.id})")
        
        print(f"\n   ✅ 共创建 {len(created_trades)} 条交易\n")
    
    # 4. 演示搜索功能
    print("🔍 步骤 4: 演示搜索功能...\n")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 4.1 搜索所有出票
        print("   📌 搜索所有出票信息:")
        sell_trades = service.search_trades(trade_type=TradeType.SELL)
        for trade in sell_trades:
            print(f"      • {trade.show_name} - ¥{trade.price} - {trade.seat_info or '无座位信息'}")
        
        # 4.2 搜索特定剧目
        print("\n   📌 搜索'女巫'相关交易:")
        wicked_trades = service.search_trades(show_name="女巫")
        for trade in wicked_trades:
            type_name = {"sell": "出", "buy": "求", "exchange": "换"}[trade.type.value]
            print(f"      • [{type_name}] {trade.show_name} - ¥{trade.price}")
        
        # 4.3 搜索特定用户的交易
        print("\n   📌 搜索 user001 的所有交易:")
        user_trades = service.search_trades(user_id="user001")
        for trade in user_trades:
            print(f"      • {trade.show_name} - {trade.type.value}")
        
        print()
    
    # 5. 演示状态管理
    print("⚙️  步骤 5: 演示状态管理...\n")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        # 将第一条交易标记为已完成
        updated = service.update_trade_status(1, TradeStatus.COMPLETED)
        print(f"   ✅ 交易 #{updated.id} 状态更新为: {updated.status.value}")
        
        # 将第二条交易标记为锁定
        updated = service.update_trade_status(2, TradeStatus.LOCKED)
        print(f"   ✅ 交易 #{updated.id} 状态更新为: {updated.status.value}")
        
        print()
    
    # 6. 演示数据展示（模拟 API 响应）
    print("📊 步骤 6: 模拟 API 响应格式...\n")
    with Session(engine) as session:
        service = MarketplaceService(session)
        
        print("   GET /api/marketplace/trades?trade_type=sell&status=open\n")
        
        trades = service.search_trades(
            trade_type=TradeType.SELL,
            status=TradeStatus.OPEN,
            limit=10
        )
        
        # 模拟 API 响应（隐藏联系方式）
        results = []
        for trade in trades:
            trade_dict = trade.model_dump(mode='json')
            has_contact = bool(trade_dict.get("contact_info"))
            trade_dict["contact_info"] = None  # 隐藏
            trade_dict["has_contact"] = has_contact
            results.append(trade_dict)
        
        print("   响应数据:")
        print(f"   {{\n     \"count\": {len(results)},")
        print(f"     \"results\": [")
        for i, trade in enumerate(results):
            print(f"       {{")
            print(f"         \"id\": {trade['id']},")
            print(f"         \"show_name\": \"{trade['show_name']}\",")
            print(f"         \"price\": {trade['price']},")
            print(f"         \"seat_info\": \"{trade['seat_info']}\",")
            print(f"         \"has_contact\": {str(trade['has_contact']).lower()},")
            print(f"         \"status\": \"{trade['status']}\"")
            print(f"       }}{'' if i == len(results)-1 else ','}")
        print(f"     ]")
        print(f"   }}\n")
    
    # 7. 总结
    print("="*60)
    print("\n✨ 示例演示完成！\n")
    print("📝 关键要点:")
    print("   • 数据层: TicketTrade 模型存储所有交易信息")
    print("   • 服务层: MarketplaceService 提供 CRUD 操作")
    print("   • API 层: RESTful 端点，支持搜索、创建、更新、删除")
    print("   • 隐私保护: contact_info 默认隐藏，需登录查看")
    print("   • 权限控制: 创建需登录，修改删除仅限发布者")
    print()


if __name__ == "__main__":
    create_sample_data()
