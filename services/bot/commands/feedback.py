import logging
from typing import List, Union

from services.bot.commands.base import CommandHandler, CommandContext
from services.bot.commands.registry import register_command
from services.db.models import Feedback

log = logging.getLogger(__name__)

@register_command
class BugReportCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/bug", "/反馈"]

    @property
    def help_text(self) -> str:
        return (
            "🐛 故障反馈\n"
            "用法: /bug [描述]\n"
            "示例: /bug 查排期一直没反应"
        )

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        content = " ".join(ctx.text_args)
        if not content:
            return self.help_text
        
        try:
            with ctx.session_maker() as session:
                feedback = Feedback(
                    contact=f"QQ:{ctx.user_id} ({ctx.nickname})",
                    type="bug",
                    content=content
                )
                session.add(feedback)
                session.commit()
                session.refresh(feedback)
                return f"🐛 已收到您的 Bug 反馈。编号: #{feedback.id}\n我们会尽快排查，感谢您的支持！"
        except Exception as e:
            log.error(f"❌ Failed to save bug report: {e}")
            return "❌ 提交失败，请稍后重试。"

@register_command
class SuggestionCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/suggest", "/建议"]

    @property
    def help_text(self) -> str:
        return (
            "💡 功能建议\n"
            "用法: /suggest [建议]\n"
            "示例: /suggest 希望增加一个按剧场搜索的功能"
        )

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        content = " ".join(ctx.text_args)
        if not content:
            return self.help_text
        
        try:
            with ctx.session_maker() as session:
                feedback = Feedback(
                    contact=f"QQ:{ctx.user_id} ({ctx.nickname})",
                    type="suggestion",
                    content=content
                )
                session.add(feedback)
                session.commit()
                session.refresh(feedback)
                return f"💡 已收到您的建议。编号: #{feedback.id}\n感谢您帮助我们改进！"
        except Exception as e:
            log.error(f"❌ Failed to save suggestion: {e}")
            return "❌ 提交失败，请稍后重试。"
