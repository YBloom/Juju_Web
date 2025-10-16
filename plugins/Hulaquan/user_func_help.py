

HLQ_QUERY_CO_CASTS_NAME = "查询n位演员的同场排期"
HLQ_QUERY_CO_CASTS_DESCRIPTION = "查询n位演员的同场排期"
HLQ_QUERY_CO_CASTS_USAGE = """/同场演员 A B C [-o] [-h]
支持多名演员，用空格隔开

-o: 显示同场其他演员（扫剧系统）
-h: 仅检索呼啦圈系统中的同场演员（使用当前缓存数据）

示例：
/同场演员 张三 -o  （扫剧系统，显示其他演员）
/同场演员 张三 -h  （呼啦圈系统，显示同场演员和涉及剧目）
"""



HLQ_SWITCH_ANNOUNCER_MODE_NAME = "切换呼啦圈上新推送模式（全部）"
HLQ_SWITCH_ANNOUNCER_MODE_DESCRIPTION = "切换呼啦圈上新推送模式(全部)"
HLQ_SWITCH_ANNOUNCER_MODE_USAGE = """
/呼啦圈通知 模式编号
3：额外关注余票增减通知
2：额外关注回流通知
1：仅关注上新/补票通知
0：关闭呼啦圈上新推送
如 “/呼啦圈通知 1”，数字和“/呼啦圈通知”间有空格
"""


HLQ_QUERY_COMMAND = "/hlq"
HLQ_QUERY_NAME = "呼啦圈查询"
HLQ_QUERY_DESCRIPTION = "呼啦圈查学生票余票/数量/排期"
HLQ_QUERY_USAGE = """
/hlq 剧名 -I -C -R
-I表示不显示已售罄场次，-C表示显示卡司阵容，-R表示检测此时此刻的数据，而非定时更新的数据（但由于频繁请求容易造成请求失败或者其他问题，不建议多使用此功能）,-t表示显示票id
❗参数间需要有空格
"""

HLQ_DATE_COMMAND = "/date"
HLQ_DATE_NAME = "查询某日演出学生票余票"
HLQ_DATE_DESCRIPTION = "根据日期通过呼啦圈查询当天学生票"
HLQ_DATE_USAGE = """
/date 日期 城市
日期格式为年-月-日
如/date 2025-06-01
城市可以不写,-i表示忽略已售罄场次
"""
HLQ_NEW_REPO_NAME = "创建一个学生票座位repo"
HLQ_NEW_REPO_DESCRIPTION = "创建一个学生座位repo"
HLQ_NEW_REPO_USAGE = """
"创建一个学生座位repo，格式为:
/新建repo
剧名:
类型:
日期:
座位:
实付:
原价：
描述:
-------
例如：/新建repo
剧名:海雾
类型:学生票
日期:2025-06-11(可不填)
座位:9-7
实付:199
原价：299
描述:整体视野不错，在山顶，地板戏有遮挡(可不填)
建议直接复制格式。"
"""

HLQ_NEW_REPO_INPUT_DICT = {
    "剧名": {"name":"title", "mandatory":True},
    "类型": {"name":"category", "mandatory":False},
    "日期": {"name":"date", "mandatory":False},
    "座位": {"name":"seat", "mandatory":True},
    "实付": {"name":"price", "mandatory":True},
    "原价":{"name":"payable", "mandatory":False},
    "描述": {"name":"content", "mandatory":False},
    "qq": {"name":"user_id", "mandatory":False},
    }

HLQ_MODIFY_REPO_NAME = "修改自己的一个学生票座位repo"
HLQ_MODIFY_REPO_DESCRIPTION = "修改自己的一个学生票座位repo"
HLQ_MODIFY_REPO_USAGE = """
"修改自己的一个学生座位repo，格式为:
/修改repo
repoID:
日期:
类型:
座位:
实付:
原价：
描述:
-------
例如：/修改repo
repoID:100001
类型:早鸟票
日期:
座位:9-5
原价：299
描述:整体视野不错，在山顶，地板戏有遮挡
-------
留空或去掉该项表示不更改此项，
剧名目前不支持修改，
repoID必填，建议直接复制格式。"
"""

HLQ_MODIFY_REPO_INPUT_DICT = {
    "repoID": {"name":"repoID", "mandatory":True},
    "类型": {"name":"category", "mandatory":False},
    "日期": {"name":"date", "mandatory":False},
    "座位": {"name":"seat", "mandatory":False},
    "实付": {"name":"price", "mandatory":False},
    "原价":{"name":"payable", "mandatory":False},
    "描述": {"name":"content", "mandatory":False},
    }

HLQ_GET_REPO_NAME = "查询学生票座位repo"
HLQ_GET_REPO_DESCRIPTION = "查询学生票座位repo"
HLQ_GET_REPO_USAGE = """/查询repo 剧名 价格
例如/查询repo 连璧 199
价格可不加
或使用/查询repo -L 查询现存repo数量
"""

HLQ_REPORT_ERROR_NAME = "报错学生票座位repo"
HLQ_REPORT_ERROR_DESCRIPTION = "报错学生票座位repo"
HLQ_REPORT_ERROR_USAGE = """
/报错repo repoID 错误信息
例如/报错repo 100001 po主说错了这个价位不是只会开在第九排
repoID可在/查询repo或/我的repo中获得
"""

HLQ_MY_REPO_NAME = "获取我创建的repo"
HLQ_MY_REPO_DESCRIPTION = "获取我创建的所有repo"
HLQ_MY_REPO_USAGE = """/我的repo"""

HLQ_LATEST_REPOS_NAME = "获取最新的N个repo"
HLQ_LATEST_REPOS_DESCRIPTION = "获取最新的N个repo（N≤20）"
HLQ_LATEST_REPOS_USAGE = """/最新repo 数字\n数字必须小于等于20"""

HLQ_DEL_REPO_NAME = "删除我创建的repo"
HLQ_DEL_REPO_DESCRIPTION = "删除我创建的repo"
HLQ_DEL_REPO_USAGE = """/删除repo repoID\n不知道repoID的可以通过/我的repo查看，可以删除多个repo，用空格分开id"""

HLQ_FOLLOW_TICKET_NAME = "关注学生票"
HLQ_FOLLOW_TICKET_DESCRIPTION = "关注学生票"
HLQ_FOLLOW_TICKET_USAGE = """
/关注学生票 场次id -T -1/-2/-3
/关注学生票 剧目名 -E -1/-2/-3
/关注学生票 剧目名 -1/-2/-3
/关注学生票 演员名 -A -1/-2/-3

-1/-2/-3表示以下的推送模式，必填
-T表示关注场次id，需要输入对应的场次
-E表示关注某些剧目，需要输入对应的剧目名
-A表示关注某些演员的所有场次（自动检索现有场次并关注，新排期自动补充）

-3：关注上新/补票/回流/余票增减通知
-2：关注上新/补票/回流通知
-1：仅关注上新/补票通知

【高级功能】
1. 多结果选择：当剧目名匹配多个结果时，使用 -数字 选择
   例：/关注学生票 桑塔露琪亚 -2 -E -1  （选择第2个搜索结果）

2. 虚拟剧目：关注未上架的剧目，上架后自动迁移订阅
   例：/关注学生票 流星 -V -E -1

3. 演员关注剧目筛选：
   -I剧目1,剧目2：仅关注演员在这些剧目中的场次（白名单）
   -X剧目1,剧目2：排除演员在这些剧目中的场次（黑名单）
   
   例：/关注学生票 张沁丹 -A -I她对此,连璧 -2  （仅关注张三在她对此和连璧中的场次）
   例：/关注学生票 胥子含 -A -X海雾 -3  （关注李四所有场次，但排除海雾）

注意：此处选择的模式数字应该大于对于呼啦圈全部通知的关注（对呼啦圈全部剧目通知的设置通过/呼啦圈通知 模式编号 调整）

基础例子：
/关注学生票 10001 10002 10003 10005 -T -2
/关注学生票 连璧 海雾 她对此 -E -3
/关注学生票 张三 李四 -A -2
"""


HLQ_SWITCH_FOLLOW_MODE_PREFIX = "/上新模式"
HLQ_SWITCH_FOLLOW_MODE_NAME = "切换上新模式（所有）"
HLQ_SWITCH_FOLLOW_MODE_DESCRIPTION = "切换上新模式（所有）"
HLQ_SWITCH_FOLLOW_MODE_USAGE = """
/上新模式
"""

HLQ_VIEW_FOLLOW_NAME = "查看关注的学生票"
HLQ_VIEW_FOLLOW_DESCRIPTION = "查看当前用户关注的所有学生票（剧目或场次）"
HLQ_VIEW_FOLLOW_USAGE = """
/查看关注
列出你关注的所有剧目和场次。
剧目显示剧名，场次显示场次ID、剧名和开票时间。
"""

HLQ_UNFOLLOW_TICKET_NAME = "取消关注学生票"
HLQ_UNFOLLOW_TICKET_DESCRIPTION = "取消关注学生票（剧目、场次或演员）"
HLQ_UNFOLLOW_TICKET_USAGE = """
/取消关注学生票 场次id -T
/取消关注学生票 剧目名 -E
/取消关注学生票 剧目名
/取消关注学生票 演员名 -A

-T: 取消关注场次id，需要输入对应的场次
-E: 取消关注某些剧目，需要输入对应的剧目名
-A: 取消关注演员（不会自动删除已关注的场次）

例如：
/取消关注学生票 10001 10002 10003 10005 -T
/取消关注学生票 连璧 海雾 她对此 -E
/取消关注学生票 张三 李四 -A
"""


# ============================================
# 帮助文档 V2 系统 - 配置文件
# ============================================
# 本文件主要负责帮助文档的文本配置
# Notion 相关功能请查看 notion_help_manager.py

HELP_DOC_VERSION = "V1.2"
BOT_VERSION = "V0.8"
HELP_DOC_UPDATE_DATE = "2025-10-16"

# 帮助文档结构化数据
HELP_SECTIONS = [
    {
        "title": "📢 呼啦圈通知设置",
        "commands": [
            {
                "usage": "/呼啦圈通知 模式",
                "aliases": ["原: /上新"],
                "description": "切换呼啦圈上新推送模式（和小机器人私聊用）",
                "modes": {
                    "3": "额外关注余票增减通知",
                    "2": "额外关注回流通知",
                    "1": "仅关注上新/补票通知",
                    "0": "关闭呼啦圈上新推送"
                },
                "examples": ["/呼啦圈通知 2"],
                "notes": ["需加小机器人好友使用，加好友默认模式1", "数字和'/呼啦圈通知'间有空格"]
            }
        ]
    },
    {
        "title": "🎫 学生票订阅功能",
        "commands": [
            {
                "usage": "/关注学生票",
                "description": "关注某些剧/某些场次/演员的学生票变动（和小机器人私聊用）",
                "variants": [
                    "/关注学生票 场次id -T -1/-2/-3",
                    "/关注学生票 剧目名 -E -1/-2/-3",
                    "/关注学生票 剧目名 -1/-2/-3",
                    "/关注学生票 演员名 -A -1/-2/-3"
                ],
                "params": {
                    "-1/-2/-3": "推送模式（必填）",
                    "-T": "关注场次id（通过/hlq 剧名 -t获取场次id）",
                    "-E": "关注某些剧目",
                    "-A": "关注演员的所有场次",
                    "-V": "关注虚拟剧目（未上架的剧）",
                    "-I": "仅关注指定剧目（白名单）",
                    "-X": "排除指定剧目（黑名单）",
                    "-数字": "选择多结果中的第N个"
                },
                "modes": {
                    "-3": "关注上新/补票/回流/余票增减通知",
                    "-2": "关注上新/补票/回流通知",
                    "-1": "仅关注上新/补票通知"
                },
                "examples": [
                    "/关注学生票 10001 10002 -T -2",
                    "/关注学生票 连璧 海雾 -E -3",
                    "/关注学生票 桑塔露琪亚 -2 -E -1  (选择第2个搜索结果)",
                    "/关注学生票 画材店 -V -E -1  (未上架的剧名，要用-V)",
                    "/关注学生票 张三 -A -2  (关注演员)",
                    "/关注学生票 张三 -A -I幽灵,怪物 -1  (仅指定剧)",
                    "/关注学生票 李四 -A -X海雾 -3  (排除指定剧)"
                ],
                "notes": [
                    "模式数字应大于呼啦圈全部通知设置",
                    "演员关注会自动检索现有场次并关注",
                    "新排期上架时会自动补充演员订阅"
                ]
            },
            {
                "usage": "/取消关注学生票",
                "description": "取消关注剧目/场次/演员",
                "variants": [
                    "/取消关注学生票 场次id -T",
                    "/取消关注学生票 剧目名 -E",
                    "/取消关注学生票 演员名 -A"
                ],
                "params": {
                    "-T": "取消关注场次id",
                    "-E": "取消关注剧目",
                    "-A": "取消关注演员（不会自动删除已关注的场次）"
                },
                "examples": [
                    "/取消关注学生票 10001 10002 -T",
                    "/取消关注学生票 连璧 海雾 -E",
                    "/取消关注学生票 张三 -A"
                ]
            },
            {
                "usage": "/查看关注",
                "description": "查看自己关注了哪些剧/场次/演员"
            }
        ]
    },
    {
        "title": "🔍 查询功能",
        "commands": [
            {
                "usage": "/hlq 剧名 [模式]",
                "description": "显示呼啦圈余票和卡司",
                "params": {
                    "-i": "忽略已售罄场次",
                    "-c": "显示卡司",
                    "-t": "显示场次ID"
                },
                "examples": [
                    "/hlq 连璧 -i -c",
                    "/hlq 她对此",
                    "/hlq 末日迷途 -c"
                ],
                "notes": ["剧名支持模糊搜索"]
            },
            {
                "usage": "/date 日期 [城市]",
                "description": "显示某天所有呼啦圈学生票场次",
                "examples": ["/date 2025-07-19 上海"],
                "notes": ["日期格式必须为 年-月-日", "城市为可选参数"]
            },
            {
                "usage": "/同场演员 演员们 [模式]",
                "description": "显示演员们同场的音乐剧排期（不止呼啦圈）",
                "params": {
                    "-o": "显示同场其他演员（扫剧系统）",
                    "-h": "仅检索呼啦圈系统中的同场演员"
                },
                "examples": [
                    "/同场演员 丁辰西 陈玉婷 -o",
                    "/同场演员 毛二",
                    "/同场演员 张三 -h"
                ],
                "notes": ["演员名之间用空格分隔"]
            },
            {
                "usage": "/所有呼啦圈",
                "description": "列出所有呼啦圈现在在售学生票的剧目"
            }
        ]
    },
    {
        "title": "📝 盲盒票Repo功能",
        "commands": [
            {
                "usage": "/新建repo 内容",
                "description": "创建一个盲盒票repo",
                "notes": ["请输入 /新建repo 查看具体说明"]
            },
            {
                "usage": "/修改repo 内容",
                "description": "修改你创建的某个repo",
                "notes": ["请输入 /修改repo 查看具体帮助"]
            },
            {
                "usage": "/查询repo 剧名/-l",
                "description": "查询某剧现有的所有repo",
                "params": {
                    "-l": "显示目前各剧所有的repo数量"
                },
                "examples": ["/查询repo -l", "/查询repo 海雾"]
            },
            {
                "usage": "/我的repo",
                "description": "查询你创建的所有repo"
            },
            {
                "usage": "/删除repo repoid",
                "description": "删除你创建的某个repo"
            },
            {
                "usage": "/最新repo",
                "description": "列出最新的20个repo"
            }
        ]
    },
    {
        "title": "🏷️ 别名管理",
        "commands": [
            {
                "usage": "/alias 搜索名 别名",
                "description": "为一个剧目创建别名",
                "examples": [
                    "/alias 末日迷途 mrmt",
                    "/alias 她对此 她厌"
                ],
                "notes": ["如果用户搜索时输入的是别名，则会按照搜索名去搜索数据"]
            },
            {
                "usage": "/aliases",
                "description": "查看所有别名"
            }
        ]
    },
    {
        "title": "💬 反馈与建议",
        "commands": [
            {
                "usage": "意见反馈",
                "description": "欢迎提出您的意见和建议！",
                "notes": [
                    "如果您有任何功能建议、问题反馈或改进意见",
                    "请直接在本页面下方评论区留言",
                    "我们会认真阅读并考虑每一条反馈",
                    "感谢您的支持！❤️"
                ]
            }
        ]
    }
]


def generate_help_v2(include_header=True, format_type="text"):
    """
    生成帮助文档 V2
    
    Args:
        include_header: 是否包含版本信息头部
        format_type: 输出格式 ('text' 或 'markdown')
    
    Returns:
        str: 格式化的帮助文档
    """
    lines = []
    
    # 头部信息
    if include_header:
        lines.append("=" * 50)
        lines.append(f"📖 呼啦圈学生票机器人 - 帮助文档 {HELP_DOC_VERSION}")
        lines.append(f"🤖 Bot版本：{BOT_VERSION}")
        lines.append(f"📅 更新时间：{HELP_DOC_UPDATE_DATE}")
        lines.append(f"💡 用法：/help")
        lines.append("=" * 50)
        lines.append("")
    
    # 遍历所有功能分类
    for section in HELP_SECTIONS:
        lines.append(f"\n{'='*50}")
        lines.append(f"{section['title']}")
        lines.append(f"{'='*50}")
        
        for cmd in section['commands']:
            lines.append("")
            lines.append(f"【用法】{cmd['usage']}")
            
            # 别名
            if 'aliases' in cmd:
                lines.append(f"  {' '.join(cmd['aliases'])}")
            
            # 功能描述
            lines.append(f"【功能】{cmd['description']}")
            
            # 变体用法
            if 'variants' in cmd:
                lines.append("【格式】")
                for variant in cmd['variants']:
                    lines.append(f"  ● {variant}")
            
            # 参数说明
            if 'params' in cmd:
                lines.append("【参数】")
                for param, desc in cmd['params'].items():
                    lines.append(f"  {param}：{desc}")
            
            # 模式说明
            if 'modes' in cmd:
                lines.append("【模式】")
                for mode, desc in cmd['modes'].items():
                    lines.append(f"  {mode}：{desc}")
            
            # 示例
            if 'examples' in cmd:
                lines.append("【示例】")
                for example in cmd['examples']:
                    lines.append(f"  {example}")
            
            # 注意事项
            if 'notes' in cmd:
                lines.append("【注意】")
                for note in cmd['notes']:
                    lines.append(f"  ⚠️ {note}")
            
            lines.append("")
    
    # 尾部信息
    if include_header:
        lines.append("\n" + "=" * 50)
        lines.append("✨ 感谢使用！有问题请联系管理员")
        lines.append("=" * 50)
    
    return "\n".join(lines)


def generate_help_v2_image():
    """
    生成帮助文档图片（需要PIL库）
    
    Returns:
        bytes: 图片二进制数据，如果失败返回None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # 生成文本
        text = generate_help_v2(include_header=True, format_type="text")
        
        # 图片配置
        font_size = 16
        line_height = font_size + 8
        padding = 40
        max_width = 1200
        
        # 计算图片尺寸
        lines = text.split('\n')
        img_height = len(lines) * line_height + padding * 2
        
        # 创建图片
        img = Image.new('RGB', (max_width, img_height), color='white')
        draw = ImageDraw.Draw(img)
        
        # 尝试使用系统字体
        try:
            # Windows
            font = ImageFont.truetype("msyh.ttc", font_size)
        except:
            try:
                # Linux
                font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", font_size)
            except:
                # 默认字体
                font = ImageFont.load_default()
        
        # 绘制文本
        y = padding
        for line in lines:
            draw.text((padding, y), line, fill='black', font=font)
            y += line_height
        
        # 转换为字节流
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr.getvalue()
    
    except ImportError:
        print("警告：PIL库未安装，无法生成图片格式帮助文档")
        return None
    except Exception as e:
        print(f"生成帮助文档图片时出错：{e}")
        return None


# 帮助文档缓存
_help_cache = {
    "text": None,
    "image": None,
    "last_update": None
}


def get_help_v2(force_refresh=False, as_image=False):
    """
    获取帮助文档（带缓存）
    
    Args:
        force_refresh: 是否强制刷新缓存
        as_image: 是否返回图片格式
    
    Returns:
        str or bytes: 帮助文档文本或图片数据
    """
    global _help_cache
    
    cache_key = "image" if as_image else "text"
    
    # 检查缓存
    if not force_refresh and _help_cache[cache_key] is not None:
        return _help_cache[cache_key]
    
    # 生成新内容
    if as_image:
        content = generate_help_v2_image()
        if content is None:
            # 图片生成失败，返回文本
            return get_help_v2(force_refresh=force_refresh, as_image=False)
    else:
        content = generate_help_v2(include_header=True, format_type="text")
    
    # 更新缓存
    _help_cache[cache_key] = content
    import datetime
    _help_cache["last_update"] = datetime.datetime.now()
    
    return content

