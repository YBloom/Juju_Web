from typing import List, Union
from services.bot.commands.base import CommandHandler, CommandContext
from services.bot.commands.registry import register_command, registry

@register_command
class HelpCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/help", "/帮助", "/菜单"]

    @property
    def help_text(self) -> str:
        return "显示帮助菜单"

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        WEB_BASE_URL = "https://yyj.yaobii.com"
        return (
            f"📖 剧剧 BOT 帮助文档已升级！\n\n"
            f"为了提供更好的阅读体验，我们将帮助文档迁移到了 Web 端。\n"
            f"请点击下方链接查看完整命令说明：\n\n"
            f"👉 {WEB_BASE_URL}/help\n\n"
            f"常用指令速查：\n"
            f"• 查排期: /date [日期]\n"
            f"• 查剧目: /hlq [剧名]\n"
            f"• 查同场演员: /cast [演员1] [演员2]\n"
            f"• 关注学生票: /关注学生票 [剧名/-A 演员] [模式0-5]\n"
            f"• 取消关注学生票: /取消关注学生票 [剧名/-A 演员]\n"
            f"• 查看通知设置: /查看关注\n"
            f"• 设置通知: /呼啦圈通知 [0-5]\n"
            f"• 反馈Bug: /bug [问题描述]\n"
            f"• 提建议: /suggest [建议内容]\n"
            f"• 登录Web: /web"
        )
