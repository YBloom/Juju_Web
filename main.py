# ========= 导入必要模块 ==========
from ncatbot.core import BotClient, GroupMessage, PrivateMessage, BaseMessage
from ncatbot.utils import get_log


# ========== 创建 BotClient ==========
bot = BotClient()
_log = get_log()

HELLOWORDS = ["哈咯","Hi","测试","哈喽","Hello","剧剧"]
VERSION = "1.0"

# ========= 注册回调函数 ==========
@bot.group_event()
async def on_group_message(msg: GroupMessage):
    _log.info(msg)
    if msg.raw_message == "测试":
        await msg.reply(text="NcatBot 测试成功喵~")

@bot.private_event()
async def on_private_message(msg: PrivateMessage):
    _log.info(msg)
    key, args = parse_args_of_messages(msg)
    if key:
        if any(word in key for word in HELLOWORDS):
            for m in hello_message():
                await bot.api.post_private_msg(msg.user_id, text=m)
    else:
        pass
    
        
@bot.request_event()
async def handle_request(self, msg):
    comment = msg.comment
    if msg.request_type == "friend": 
        if "剧剧" in comment:
            self.users_manager.add_user(msg.user_id)
            await msg.reply(True, comment="加好友请求已通过")
            for m in hello_message():
                await bot.api.post_private_msg(msg.user_id, text=m)
        else:
            await msg.reply(False, comment="加好友请求被拒绝")
    else:
        self.groups_manager.add_group(msg.group_id)
        await msg.reply(True, comment="加群请求已通过")

def hello_message():
    msg = []
    msg.append(f"""
    哈咯我是剧剧机器人，致力于便捷广大zgyyj韭菜（划掉）查学生票查排期，目前只是初步实现，更多功能欢迎大家多多提议！\n
    当前版本：v{VERSION}\n
    目前已经实现的功能有：\n
    ✅1./hlq <剧名> <-i> <-c> 查某剧呼啦圈余票/数量/卡司\n
    -i表示忽略已售罄场次,-c表示显示排期对应卡司\n
    如：/hlq 丽兹 -c
    ✅2./上新 <0/1/2> 关注/取消关注呼啦圈上新推送\n
    /上新后的数字参数表示推送模式：0为不接受推送,1为只推送更新消息,2为推送每次检测结果(30秒一次，会很烦)
    ✅3./date <日期> 返回扫剧查排期的网址\n
    日期格式为 YYYY-MM-DD\n
    如：/date 2025-06-23\n
    ✅4./help Hulaquan 获取指令帮助文档
    """)
    msg.append(f"""
    ❗由于考虑到机器人服务的稳定性和快速性，有些数据更新可能并不及时，以下是各数据更新时间：\n
    ❗呼啦圈数据：30秒查询一次\n
    ❗呼啦圈余票的卡司数据：12小时查询一次\n
    🟢有想要的功能可以在主包的小红书留言！欢迎nin来！
    🟡主包技术有限，机器人试运行初期可能会有各种问题烦请大家见谅，如有问题或体验问题欢迎多多反馈，实时数据以呼啦圈官网和扫剧（http://y.saoju.net/yyj/）为准。\n
    ~~最后祝大家有钱有票！剧场见！~~
    """)
    return msg
        
        
def parse_args_of_messages(message: BaseMessage):
    """
    解析消息中的参数
    :param message: BaseMessage 消息对象
    :return: 参数列表
    """
    args = []
    if message.raw_message:
        args = message.raw_message.split(' ')
        return args[0], args[1:] if len(args) > 1 else []
    return None, []

# ========== 启动 BotClient==========

if __name__ == "__main__":
    bot.run(bt_uin="3044829389", root="3022402752", enable_webui_interaction=False) # 这里写 Bot 的 QQ 号