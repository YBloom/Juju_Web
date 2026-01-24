from typing import List, Optional, Dict
import logging

log = logging.getLogger(__name__)

# 事件类型对应的最低触发级别
# Mode 1: 上新 (new, pending)
# Mode 2: 上新+补票 (restock)
# Mode 3: 上新+补票+回流 (back)
# Mode 4: 上新+补票+回流+余票减 (stock_change 且 票数减少)
# Mode 5: 全部 (stock_change 且 票数增加, sold_out)

EVENT_LEVEL_MAP = {
    "new": 1,
    "pending": 1,
    "add": 2,      # 补票级别
    "restock": 2,  # 回流级别 (0->正)
    "back": 3,     # 票增级别
    "sold_out": 5,      # 售罄属于全部变动
    "stock_change": 4,  # 默认余票变动为 4
}

MODE_DESCRIPTIONS = {
    0: "关闭",
    1: "开票",
    2: "开票+补票/回流",
    3: "开票+补票/回流+票增",
    4: "开票+补票/回流+票增+票减",
    5: "全部"
}

def should_notify(global_level: int, notification_level: int, update: dict, targets: list) -> bool:
    """
    判断是否应该推送通知
    :param global_level: 用户全局推送级别 (User.global_notification_level)
    :param notification_level: 订阅特定的推送级别 (User.global_notification_level)
    :param update: 包含 change_type, event_id, cast_names, old_stock, new_stock 等信息的字典
    :param targets: SubscriptionTarget 对象列表
    :return: bool
    """
    # 按照需求：特定订阅级别必须 >= 全局级别。如果没设置，使用全局。
    effective_level = max(global_level, notification_level)
    
    if effective_level == 0:
        return False

    change_type = update.get("change_type")
    required_level = EVENT_LEVEL_MAP.get(change_type, 5)

    # 针对 Mode 4 和 Mode 5 的特殊处理 (余票增减)
    if change_type == "stock_change":
        old_stock = update.get("old_stock", 0)
        new_stock = update.get("new_stock", 0)
        if new_stock < old_stock:
            # 余票减少
            required_level = 4
        else:
            # 余票增加
            required_level = 5

    # 1. 首先检查是否有目标匹配
    matched_target = None
    for target in targets:
        if _matches_target(target, update):
            matched_target = target
            break
    
    # 如果没有目标匹配，则不推送（因为这是订阅系统，只推送订阅成功的）
    # 注意：全局推送由 bot 逻辑处理，这里只处理具体订阅的过滤
    if not matched_target:
        return False

    # 2. 如果匹配了目标，检查白名单/黑名单 (针对演员订阅)
    if matched_target.kind == "actor":
        event_id = update.get("event_id")
        # 这里的 include_plays/exclude_plays 预计是 list 或 dict
        include = matched_target.include_plays
        exclude = matched_target.exclude_plays
        
        if include and isinstance(include, list) and event_id not in include:
            return False
        if exclude and isinstance(exclude, list) and event_id in exclude:
            return False

    # 3. 检查级别
    return effective_level >= required_level

def _matches_target(target, update: dict) -> bool:
    """检查更新是否匹配订阅目标"""
    target_kind = target.kind
    target_id = target.target_id
    
    if target_kind == "play":
        # 剧目订阅
        if target_id == update.get("event_id"):
            # 城市过滤
            if target.city_filter and target.city_filter != update.get("city"):
                return False
            return True
            
    elif target_kind == "actor":
        # 演员订阅
        cast_names = update.get("cast_names", [])
        if target_id in cast_names:
            return True
            
    elif target_kind == "event":
        # 特定场次订阅 (旧版兼容)
        if target_id == update.get("ticket_id"):
            return True
            
    elif target_kind == "keyword":
        # 关键词订阅 (Global)
        name = target.name or ""
        if name.lower() in update.get("title", "").lower():
            return True

    return False
