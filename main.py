# ========= 导入必要模块 ==========
from ncatbot.core import BotClient, GroupMessage, PrivateMessage, BaseMessage
from ncatbot.utils import get_log


# ========== 创建 BotClient ==========
bot = BotClient()
_log = get_log()

HELLOWORDS = ["哈咯","Hi","测试","哈喽","Hello","剧剧"]
VERSION = "1.0"
bot_qq = "3044829389"

# ========= 注册回调函数 ==========
@bot.group_event()
async def on_group_message(msg: GroupMessage):
    if int(msg.user_id) != int(bot_qq):
        _log.info(msg)

@bot.private_event()
async def on_private_message(msg: PrivateMessage):
    if int(msg.user_id) != int(bot_qq):
        _log.info(msg)
        

# ========== 启动 BotClient==========

if __name__ == "__main__":
    from ncatbot.utils import config
    # 设置 WebSocket 令牌
    #config.set_ws_token("ncatbot_ws_token")

    bot.run(bt_uin=bot_qq, root="3022402752", enable_webui_interaction=False) # 这里写 Bot 的 QQ 号