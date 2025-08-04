# commands/parser.py
import shlex
from .registry import BY_TRIGGER, Flag
from models import *

class UnknownCommand(Exception):
    pass

class MissingFlagValue(Exception):
    pass

def parse_message(msg: str) -> tuple[Command, dict[str, str | bool]]:
    """
    /hlq 连璧 -I -C → (Command, {"drama": "连璧", "hide_soldout": True, "show_casts": True})
    """
    parts = shlex.split(msg)
    trigger = parts[0]
    cmd = BY_TRIGGER.get(trigger)
    if not cmd:
        raise UnknownCommand(trigger)

    args_iter = iter(parts[1:])
    parsed: dict[str, str | bool] = {}
    # 默认值
    for f in cmd.flags:
        if f.default is not None:
            parsed[f.key] = f.default

    for token in args_iter:
        # flag?
        if any(token == f.token for f in cmd.flags):
            f: Flag = next(f for f in cmd.flags if f.token == token)
            if f.takes_value:
                try:
                    value = next(args_iter)
                except StopIteration:
                    raise MissingFlagValue(token)
                parsed[f.key] = value
            else:
                parsed[f.key] = True
        else:
            # 第一个非 flag 视为“主题词”（drama / actor...）
            parsed.setdefault("keyword", token)

    return cmd, parsed
