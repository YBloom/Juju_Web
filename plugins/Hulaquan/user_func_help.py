


HLQ_SWITCH_ANNOUNCER_MODE_NAME = "切换呼啦圈上新推送模式"
HLQ_SWITCH_ANNOUNCER_MODE_DESCRIPTION = "切换呼啦圈上新推送模式"
HLQ_SWITCH_ANNOUNCER_MODE_USAGE = """
/上新 模式编号
2：关注呼啦圈检测的推送（定时检测一次并通知）
1（推荐）：仅关注上新通知
0：关闭呼啦圈上新推送
如“/上新 1”，数字和“上新”间有空格
"""


HLQ_QUERY_COMMAND = "/hlq"
HLQ_QUERY_NAME = "呼啦圈查询"
HLQ_QUERY_DESCRIPTION = "呼啦圈查学生票余票/数量/排期"
HLQ_QUERY_USAGE = """
/hlq 剧名 -I -C -R
-I表示不显示已售罄场次，-C表示显示卡司阵容，-R表示检测此时此刻的数据，而非定时更新的数据（但由于频繁请求容易造成请求失败或者其他问题，不建议多使用此功能）
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
日期:
座位:
价格:
描述:
-------
例如：/新建repo
剧名:海雾
日期:2025-06-11(可不填)
座位:9-7
价格:199
描述:整体视野不错，在山顶，地板戏有遮挡(可不填)
建议直接复制格式。"
"""

HLQ_MODIFY_REPO_NAME = "修改自己的一个学生票座位repo"
HLQ_MODIFY_REPO_DESCRIPTION = "修改自己的一个学生票座位repo"
HLQ_MODIFY_REPO_USAGE = """
"修改自己的一个学生座位repo，格式为:
/修改repo
repoID:
剧名:
日期:
座位:
价格:
描述:
-------
例如：/新建repo
repoID:100001
日期:
座位:9-5
描述:整体视野不错，在山顶，地板戏有遮挡
-------
留空或去掉该项表示不更改此项，
剧名目前不支持修改，
repoID必填，建议直接复制格式。"
"""

HLQ_GET_REPO_NAME = "获取学生票座位repo"
HLQ_GET_REPO_DESCRIPTION = "获取学生票座位repo"
HLQ_GET_REPO_USAGE = """/查询repo 剧名 价格
例如/查询repo 连璧 199
价格可不加
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