"""
统一时区管理模块
所有时间相关操作必须使用此模块，确保时区一致性

使用方法:
    from services.utils.timezone import now
    
    # 获取当前UTC+8时间
    current_time = now()
"""
from datetime import datetime
from zoneinfo import ZoneInfo

# 全局时区配置 - UTC+8 (北京时间/中国标准时间)
TIMEZONE = ZoneInfo("Asia/Shanghai")

def now():
    """
    获取当前时间 (UTC+8)
    替代 datetime.now()
    
    Returns:
        datetime: 带时区信息的当前时间 (Asia/Shanghai, UTC+8)
    
    Example:
        >>> current = now()
        >>> print(current)
        2026-01-04 23:16:48.123456+08:00
    """
    return datetime.now(TIMEZONE)

def utcnow():
    """
    获取当前UTC时间 (仅用于需要UTC的场景)
    
    Returns:
        datetime: 带时区信息的当前UTC时间
    """
    from datetime import timezone as tz
    return datetime.now(tz.utc)

def make_aware(dt: datetime) -> datetime:
    """
    将naive datetime转换为aware datetime (UTC+8)
    
    Args:
        dt: naive datetime对象
        
    Returns:
        datetime: 带UTC+8时区信息的datetime
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TIMEZONE)
    return dt

def to_local(dt: datetime) -> datetime:
    """
    将任意时区的datetime转换为UTC+8
    
    Args:
        dt: 任意时区的datetime
        
    Returns:
        datetime: 转换为UTC+8的datetime
    """
    if dt.tzinfo is None:
        # 假设naive datetime是UTC+8
        return dt.replace(tzinfo=TIMEZONE)
    return dt.astimezone(TIMEZONE)
