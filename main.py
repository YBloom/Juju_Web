# ========= 导入必要模块 ==========
from ncatbot.core import BotClient, GroupMessage, PrivateMessage, BaseMessage
from ncatbot.utils import get_log


# ========== 创建 BotClient ==========
bot = BotClient()
_log = get_log()

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
        if "测试" in msg.raw_message:
            await bot.api.post_private_msg(msg.user_id, text="NcatBot 测试成功喵~")
    else:
        pass
        
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
    bot.run(bt_uin="3044829389", root="3022402752") # 这里写 Bot 的 QQ 号