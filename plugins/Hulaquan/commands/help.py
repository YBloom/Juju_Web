# commands/help.py
from .registry import COMMANDS

def render_all_help() -> str:
    lines = []
    for cmd in COMMANDS:
        lines.append(f"{cmd.trigger} — {cmd.name}")
        lines.append(f"{cmd.description}")
        lines.append(cmd.usage_text())
        if cmd.flags:
            lines.append("可选参数：")
            for f in cmd.flags:
                suffix = f" <{f.value_hint}>" if (f.takes_value and f.value_hint) else ""
                lines.append(f"  {f.token}{suffix}  {f.description}")
        if cmd.examples:
            lines.append("示例：")
            for e in cmd.examples:
                lines.append(f"  {e}")
        lines.append("")  # 空行
    return "\n".join(lines).rstrip()
