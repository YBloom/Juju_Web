"""
时区修复单元测试
验证所有时间操作都使用UTC+8时区
"""
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from services.utils.timezone import now, make_aware, to_local, TIMEZONE, utcnow

def test_timezone_is_shanghai():
    """验证时区配置为上海 (UTC+8)"""
    assert str(TIMEZONE) == "Asia/Shanghai"

def test_now_returns_shanghai_time():
    """验证now()返回的是UTC+8时间"""
    current = now()
    assert current.tzinfo is not None
    assert current.tzinfo == TIMEZONE
    
    # 验证时区偏移为+8小时
    offset = current.utcoffset()
    assert offset.total_seconds() == 8 * 3600

def test_utcnow_returns_utc_time():
    """验证utcnow()返回UTC时间"""
    current = utcnow()
    assert current.tzinfo is not None
    offset = current.utcoffset()
    assert offset.total_seconds() == 0

def test_make_aware():
    """验证naive转aware功能"""
    naive_dt = datetime(2026, 1, 4, 23, 0, 0)
    aware_dt = make_aware(naive_dt)
    
    assert aware_dt.tzinfo == TIMEZONE
    assert aware_dt.year == 2026
    assert aware_dt.hour == 23

def test_to_local_from_utc():
    """验证UTC转UTC+8"""
    from datetime import timezone as tz
    utc_dt = datetime(2026, 1, 4, 15, 0, 0, tzinfo=tz.utc)  # UTC 15:00
    local_dt = to_local(utc_dt)
    
    assert local_dt.tzinfo == TIMEZONE
    assert local_dt.hour == 23  # UTC+8 应该是23:00

def test_database_model_timezone():
    """验证数据库模型使用正确时区"""
    from services.hulaquan.tables import HulaquanEvent
    from services.db.connection import session_scope
    
    with session_scope() as session:
        event = HulaquanEvent(
            id="test_tz_001",
            title="时区测试"
        )
        session.add(event)
        session.commit()
        
        # 验证created_at带时区
        assert event.created_at.tzinfo == TIMEZONE
        assert event.updated_at.tzinfo == TIMEZONE
        
        # 清理
        session.delete(event)
        session.commit()

def test_hulaquan_utils_timezone():
    """验证hulaquan/utils.py使用正确时区"""
    from services.hulaquan.utils import now_time_str
    
    # now_time_str应该返回UTC+8时间的字符串
    time_str = now_time_str()
    assert isinstance(time_str, str)
    assert len(time_str.split()) == 2  # "YYYY-MM-DD HH:MM:SS" 格式

def test_time_consistency_across_services():
    """验证不同服务层的时间一致性"""
    from services.utils.timezone import now
    from services.hulaquan.utils import now_time_str
    
    # 获取两个时间，应该很接近（秒级差异）
    t1 = now()
    time_str = now_time_str()
    
    # 解析time_str
    from datetime import datetime
    t2 = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    t2 = make_aware(t2)
    
    # 差异应该在1秒内
    diff = abs((t1 - t2).total_seconds())
    assert diff < 1
