# commands/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from textwrap import dedent
from typing import Optional, Tuple

class CommandId(StrEnum):
    HLQ_QUERY_CO_CASTS = "hlq.query.co_casts"
    HLQ_SWITCH_ANNOUNCER_MODE = "hlq.switch.announcer_mode"
    HLQ_QUERY = "hlq.query"

class AnnouncerMode(IntEnum):
    OFF = 0              # 关闭
    NOTIFY = 1           # 仅关注上新通知（推荐）
    DETECT_AND_NOTIFY = 2# 关注呼啦圈检测的推送（定时检测+通知）

@dataclass(frozen=True)
class Flag:
    token: str               # 如 "-o" / "-I"
    key: str                 # 代码里使用的内部键，如 "show_other"
    description: str
    takes_value: bool = False
    value_hint: Optional[str] = None   # 如果需要值，如 "-m 1"
    default: Optional[str | int | bool] = None

@dataclass(frozen=True)
class Command:
    id: CommandId
    trigger: str                 # 触发词，如 "/hlq"、"/同场演员"、"/上新"
    name: str                    # 展示名
    description: str
    usage: str                   # 多行使用说明
    flags: Tuple[Flag, ...] = field(default_factory=tuple)
    examples: Tuple[str, ...] = field(default_factory=tuple)
    category: str = "hlq"

    def usage_text(self) -> str:
        return dedent(self.usage).strip()
