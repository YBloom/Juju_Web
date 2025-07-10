


HLQ_SWITCH_ANNOUNCER_MODE_NAME = "切换呼啦圈上新推送模式"
HLQ_SWITCH_ANNOUNCER_MODE_DESCRIPTION = "切换呼啦圈上新推送模式"
HLQ_SWITCH_ANNOUNCER_MODE_USAGE = """
/上新 模式编号\n
2：关注呼啦圈检测的推送（定时检测一次并通知）\n
1（推荐）：仅关注上新通知\n
0：关闭呼啦圈上新推送\n
如“/上新 1”，数字和“上新”间有空格
"""


HLQ_QUERY_COMMAND = "/hlq"
HLQ_QUERY_NAME = "呼啦圈查询"
HLQ_QUERY_DESCRIPTION = "呼啦圈查学生票余票/数量/排期"
HLQ_QUERY_USAGE = """
/hlq 剧名 -I -C -R\n
-I表示不显示已售罄场次，
-C表示显示卡司阵容，
-R表示检测此时此刻的数据，
而非定时更新的数据（但由于频繁请求容易造成请求失败或者其他问题，不建议多使用此功能）\n
❗参数间需要有空格
"""

HLQ_DATE_COMMAND = "/date"
HLQ_DATE_NAME = "查询某日演出学生票余票"
HLQ_DATE_DESCRIPTION = "根据日期通过呼啦圈查询当天学生票"
HLQ_DATE_USAGE = """
/date 日期 城市\n
日期格式为年-月-日\n
如/date 2025-06-01\n
城市可以不写,-i表示忽略已售罄场次
"""
HLQ_NEW_REPO_NAME = "创建一个学生座位repo"
HLQ_NEW_REPO_DESCRIPTION = "创建一个学生座位repo"
HLQ_NEW_REPO_USAGE = """
"创建一个学生座位repo，格式为：\n 
/学生票座位记录\n
剧名:\n
日期:\n
座位:\n
价格:\n
描述:\n\n
例如：/学生票座位记录\n
剧名:海雾\n
日期:2025-06-11(可不填)\n
座位:9-7\n
价格:199\n
描述:整体视野不错，在山顶，地板戏有遮挡(可不填)\n
建议直接复制格式。"
"""