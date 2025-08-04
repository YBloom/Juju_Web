# commands/registry.py
from .models import Command, Flag, CommandId, AnnouncerMode

CO_CASTS = Command(
    id=CommandId.HLQ_QUERY_CO_CASTS,
    trigger="/同场演员",
    name="查询n位演员的同场排期",
    description="查询多名演员的同场排期",
    usage="""
/同场演员 A B C -o
支持多名演员，用空格隔开
-o 表示显示同场其他演员
""",
    flags=(
        Flag(token="-o", key="show_other", description="显示同场其他演员"),
    ),
    examples=(
        "/同场演员 张三 李四 -o",
        "/同场演员 王一 王二",
    ),
)

SWITCH_ANNOUNCER_MODE = Command(
    id=CommandId.HLQ_SWITCH_ANNOUNCER_MODE,
    trigger="/呼啦圈通知",
    name="切换呼啦圈上新推送模式（全部）",
    description="切换呼啦圈上新推送模式（全部）",
    usage="""
/呼啦圈通知 模式编号
3：额外关注余票增减通知
2：额外关注回流通知
1：仅关注上新/补票通知
0：关闭呼啦圈上新推送
如 “/呼啦圈通知 1”，数字和“/呼啦圈通知”间有空格
""",
    flags=(
        Flag(token="-m", key="mode", description="上新推送模式", takes_value=True, value_hint="0|1|2", default=1),
    ),
    examples=("/呼啦圈通知 1", "/呼啦圈通知 0"),
)

HLQ_QUERY = Command(
    id=CommandId.HLQ_QUERY,
    trigger="/hlq",
    name="呼啦圈查询",
    description="呼啦圈查学生票余票/数量/排期",
    usage="""
/hlq 剧名 -I -C -R
-I 表示不显示已售罄场次
-C 表示显示卡司阵容
-R 表示检测此时此刻的数据（不建议频繁使用）
❗参数间需要有空格
""",
    flags=(
        Flag(token="-I", key="hide_soldout", description="不显示已售罄场次"),
        Flag(token="-C", key="show_casts", description="显示卡司阵容"),
        Flag(token="-R", key="realtime", description="实时检测"),
    ),
    examples=(
        "/hlq 连璧 -I -C",
        "/hlq 怪物 -R",
    ),
)

# 导出总注册表：列表或字典
COMMANDS: tuple[Command, ...] = (CO_CASTS, SWITCH_ANNOUNCER_MODE, HLQ_QUERY)
COMMAND_BY_TRIGGER = {c.trigger: c for c in COMMANDS}
COMMAND_BY_ID = {c.id: c for c in COMMANDS}
