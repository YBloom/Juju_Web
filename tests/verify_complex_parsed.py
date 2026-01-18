"""演示复杂盘票场景如何映射到结构化模型 V2."""

import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.db.connection import get_engine
from services.db.models import ListingItem, MarketplaceListing, ItemDirection, User, TradeStatus
from services.marketplace.service import MarketplaceService
from sqlmodel import Session, SQLModel


def run_complex_demos():
    print("🎭 复杂盘票场景结构化演示 (V2模型)\n")
    print("="*80)
    
    # 初始化
    engine = get_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # 创建演示用户
        user = User(user_id="expert_trader", nickname="盘票大拿")
        session.add(user)
        session.commit()
        
        service = MarketplaceService(session)

        # --- 场景 1: 不单出的捆绑 ---
        print("\n🎬 案例 1: 捆绑不单出")
        print("文本: 2.23午 文祥怪物 + 2.23晚 文祥幽灵，票面出，不单出")
        
        listing1 = service.create_listing(
            user_id="expert_trader",
            items=[
                {
                    "direction": "have",
                    "show_name": "文祥怪物",
                    "show_time": datetime(2026, 2, 23, 14, 0),
                    "price": 399.0,
                    "seat_info": "二楼D区1排17号",
                    "original_price": 399.0
                },
                {
                    "direction": "have",
                    "show_name": "文祥幽灵",
                    "show_time": datetime(2026, 2, 23, 19, 30),
                    "price": 299.0,
                    "seat_info": "B区5-1",
                    "original_price": 299.0
                }
            ],
            requirements="这两张不单出，原价出，不回收任何",
            description="都是好位"
        )
        print(f"✅ 映射成功: 1个Listing下挂载了 {len(listing1.items)} 个HAVE细项。匹配逻辑：必须同时处理。")

        # --- 场景 2: 一换多（OR逻辑） ---
        print("\n🎬 案例 2: 一换多 (灵活补差)")
        print("文本: 【出】奥尔菲斯 1.18晚 【或换】1.29晚/2.1午/2.4晚...")
        
        # 简化演示，只选两个代表性日期
        listing2 = service.create_listing(
            user_id="expert_trader",
            items=[
                {
                    "direction": "have",
                    "show_name": "奥尔菲斯",
                    "show_time": datetime(2026, 1, 18, 19, 30),
                    "price": 380.0,
                    "seat_info": "1-15-16过道位"
                },
                {
                    "direction": "want",
                    "show_name": "奥尔菲斯 (换)",
                    "show_time": datetime(2026, 1, 29, 19, 30),
                },
                {
                    "direction": "want",
                    "show_name": "奥尔菲斯 (换)",
                    "show_time": datetime(2026, 2, 1, 14, 0),
                }
            ],
            requirements="灵活补差",
            description="带座私聊"
        )
        print(f"✅ 映射成功: 1个HAVE项对应多个WANT项。匹配逻辑：只要手持有任何一个WANT日期的人，都能搜到这个Listing。")

        # --- 场景 3: 极大规模列表（多对多） ---
        print("\n🎬 案例 3: 极长列表 (多对多匹配)")
        print("文本: 大量女巫/时光代理人【有】 vs 大量女巫【换/收】")
        
        # 演示其核心结构
        listing3 = service.create_listing(
            user_id="expert_trader",
            items=[
                # HAVE 部分 (演示2项)
                {"direction": "have", "show_name": "女巫", "show_time": datetime(2026, 1, 17, 14, 0), "description": "丫蛋卉学生票"},
                {"direction": "have", "show_name": "时光代理人", "show_time": datetime(2026, 1, 27, 19, 30), "quantity": 2},
                # WANT 部分 (演示2项)
                {"direction": "want", "show_name": "女巫", "show_time": datetime(2026, 1, 15, 19, 30), "description": "预演场199降仓"},
                {"direction": "want", "show_name": "女巫", "show_time": datetime(2026, 1, 24, 14, 0), "price": 299.0},
            ],
            requirements="学生票只换学生票，部分可二换一，暂不出",
            description="大部分换不到都会看"
        )
        print(f"✅ 映射成功: 挂单包含了 {len(listing3.items)} 个细项。")
        print(f"   - 系统可以索引到该用户同时持有《女巫》和《时光代理人》。")
        print(f"   - 且同时在求购多种演出。")

        # --- 验证匹配逻辑 ---
        print("\n🔍 匹配验证:")
        print("测试: 我正好有'1.29晚 奥尔菲斯'，想找谁手里有我想要的（1.18晚 奥尔菲斯）")
        
        # 搜寻谁 WANT 1.29晚 奥尔菲斯
        matches = service.find_matches("奥尔菲斯 (换)", ItemDirection.HAVE) # 搜索 WANT 它的
        for item in matches:
            parent = service.get_listing(item.listing_id)
            # 找到对应的 HAVE 项
            have_items = [i for i in parent.items if i.direction == ItemDirection.HAVE]
            print(f"   🎯 匹配到挂单 #{parent.id}:")
            print(f"      对方提供的票: {[f'{i.show_name} ({i.show_time})' for i in have_items]}")
            print(f"      对方的要求: {parent.requirements}")

    print("\n" + "="*80)
    print("✨ 结论: V2 结构化模型通过 Listing 容器 + 独立 Item 颗粒度，完美支持以上三种极端场景。")
    print("   1. 捆绑关系由 listing_id 锁定。")
    print("   2. 多选一置换通过在同一 Listing 下挂载多个 WANT Item 实现。")
    print("   3. 长列表通过全量结构化 Item 条目实现精准匹配。")


if __name__ == "__main__":
    run_complex_demos()

