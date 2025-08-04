

HLQ_QUERY_CO_CASTS_NAME = "查询n位演员的同场排期"
HLQ_QUERY_CO_CASTS_DESCRIPTION = "查询n位演员的同场排期"
HLQ_QUERY_CO_CASTS_USAGE = """/同场演员 A B C -o
支持多名演员，用空格隔开
-o表示显示同场其他演员
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

-1/-2/-3表示以下的推送模式，必填
-T表示关注场次id，需要输入对应的场次
-E表示关注某些剧目，需要输入对应的剧目名

3：额外关注余票增减通知
2：额外关注回流通知
1：仅关注上新/补票通知

注意：此处选择的模式数字应该大于对于呼啦圈全部通知的关注（对呼啦圈全部剧目通知的设置通过/呼啦圈通知 模式编号 调整）

例如：/关注学生票 10001 10002 10003 10005 -T -2
/关注学生票 连璧 海雾 她对此 -E -3
"""


HLQ_SWITCH_FOLLOW_MODE_PREFIX = "/上新模式"
HLQ_SWITCH_FOLLOW_MODE_NAME = "切换上新模式（所有）"
HLQ_SWITCH_FOLLOW_MODE_DESCRIPTION = "切换上新模式（所有）"
HLQ_SWITCH_FOLLOW_MODE_USAGE = """
/上新模式
"""