"""
Notification Configuration & Constants
集中管理通知等级、变更类型映射及显示前缀。
"""
from enum import IntEnum
from typing import Dict

class NotificationLevel(IntEnum):
    OFF = 0
    NEW_ONLY = 1  # 仅通知 上新
    RECOMMENDED = 2  # 上新 + 补票 (★推荐)
    INCLUDE_RESTOCK = 3  # 上新 + 补票 + 回流
    INCLUDE_DECREASE = 4  # 上新 + 补票 + 回流 + 票减
    ALL_CHANGES = 5  # 上新 + 补票 + 回流 + 票增 + 票减 (全部变动)

# 模式描述 (用于帮助文档)
MODE_DESCRIPTIONS: Dict[int, str] = {
    NotificationLevel.OFF: "无通知",
    NotificationLevel.NEW_ONLY: "仅通知 上新",
    NotificationLevel.RECOMMENDED: "上新 + 补票 (★推荐)",
    NotificationLevel.INCLUDE_RESTOCK: "上新 + 补票 + 回流",
    NotificationLevel.INCLUDE_DECREASE: "上新 + 补票 + 回流 + 票减",
    NotificationLevel.ALL_CHANGES: "上新 + 补票 + 回流 + 票增 + 票减 (全部变动)"
}

# 变更类型 -> 最低通知等级 映射
# 决定了某种类型的变动至少需要用户设定什么等级才会收到
CHANGE_TYPE_LEVEL_MAP: Dict[str, int] = {
    "new": NotificationLevel.NEW_ONLY,
    "pending": NotificationLevel.NEW_ONLY,    # 待开票
    "add": NotificationLevel.RECOMMENDED,     # 补票 (总票数增加)
    "restock": NotificationLevel.INCLUDE_RESTOCK, # 回流 (0->正)
    "decrease": NotificationLevel.INCLUDE_DECREASE, # 票减
    "stock_decrease": NotificationLevel.INCLUDE_DECREASE, 
    "back": NotificationLevel.ALL_CHANGES,       # 票增 (正->更多)
    "increase": NotificationLevel.ALL_CHANGES,   # 票增
    "stock_increase": NotificationLevel.ALL_CHANGES,
    "sold_out": 99,  # 暂不推送售罄，除非特定处理
}

# 变更类型 -> 显示前缀 映射
TYPE_PREFIX_MAP: Dict[str, str] = {
    "new": "🆕上新",
    "add": "🟢补票",
    "restock": "♻️回流",
    "back": "➕票增",
    "increase": "➕票增",
    "stock_increase": "➕票增",
    "decrease": "➖票减",
    "stock_decrease": "➖票减",
    "sold_out": "❗售罄",
    "pending": "⏲️待开票",
}

# 变更类型排序优先级 (用于消息合并时的展示顺序)
TYPE_SORT_ORDER = [
    "new", 
    "restock", 
    "add", 
    "back", 
    "increase",
    "stock_increase",
    "decrease", 
    "stock_decrease",
    "pending", 
    "sold_out"
]
