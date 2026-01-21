"""Compat aware accessors for Hulaquan's legacy data managers.
用于 Hulaquan 旧版数据管理器的兼容访问器。
"""

from __future__ import annotations

from typing import Optional

from ncatbot.utils.logger import get_log

from services.compat import CompatContext

from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
from plugins.Hulaquan.StatsDataManager import StatsDataManager
from plugins.Hulaquan.AliasManager import AliasManager
from plugins.Hulaquan.HulaquanDataManager import HulaquanDataManager
from plugins.AdminPlugin.UsersManager import UsersManager

log = get_log()

try:
    User = UsersManager()
    Alias = AliasManager()
    Stats = StatsDataManager()
    Saoju = SaojuDataManager()
    Hlq = HulaquanDataManager()
except RuntimeError:
    # Handle cases where no event loop is running during import
    User = None
    Alias = None
    Stats = None
    Saoju = None
    Hlq = None

_CURRENT_CONTEXT = None
try:
    _CURRENT_CONTEXT = CompatContext(
        users=User,
        alias=Alias,
        stats=Stats,
        saoju=Saoju,
        hulaquan=Hlq,
    )
except Exception:
    pass


def use_compat_context(context: Optional[CompatContext]) -> CompatContext:
    """Install a compat context for module level manager references.
    为模块级管理器引用安装兼容上下文。
    """

    global _CURRENT_CONTEXT, User, Alias, Stats, Saoju, Hlq
    if context is None:
        context = _CURRENT_CONTEXT
    else:
        _CURRENT_CONTEXT = context
    User = context.users
    Alias = context.alias
    Stats = context.stats
    Saoju = context.saoju
    Hlq = context.hulaquan
    return context


def current_context() -> CompatContext:
    return _CURRENT_CONTEXT


async def save_all(on_close: bool = False) -> bool:
    """Persist every manager tracked by the active context.
    持久化活动上下文跟踪的每个管理器。
    """

    return await _CURRENT_CONTEXT.save_all(on_close)