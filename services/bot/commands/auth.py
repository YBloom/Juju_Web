import os
import jwt
from typing import List, Union
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from services.bot.commands.base import CommandHandler, CommandContext
from services.bot.commands.registry import register_command

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "musicalbot-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 5
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://yyj.yaobii.com")

def create_magic_link_token(qq_id: str, nickname: str = "") -> str:
    """Generate Magic Link Token for Bot User"""
    payload = {
        "qq_id": qq_id,
        "nickname": nickname,
        "exp": datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(ZoneInfo("Asia/Shanghai")),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

@register_command
class WebLoginCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/web", "/login", "/登录", "登录", "登陆"]

    @property
    def help_text(self) -> str:
        return "获取 Web 控制台登录链接 (Magic Link)"

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        # For login token, we act on the raw QQ ID (if available context) or User ID.
        # handlers.py passed user_id as argument, which for new users is 6 digits.
        # But for magic link we often want to bind the QQ ID.
        # ctx.user_id is the canonical ID.
        # ctx.nickname is available.
        
        # However, create_magic_link_token expects `qq_id`.
        # If the user is already authenticated/standardized, `ctx.user_id` might be the mapped 6-digit ID.
        # The frontend/auth service needs to handle this token.
        # The original code: token = create_magic_link_token(uid_str, nickname)
        # where uid_str was str(user_id) passed from handle_group_message.
        
        token = create_magic_link_token(ctx.user_id, ctx.nickname)
        link = f"{WEB_BASE_URL}/auth/magic-link?token={token}"
        return [
            (
                f"🔐 点击下方链接登录 Web 控制台（5分钟内有效）：\n\n"
                f"✨ 登录后可查看完整演出信息、管理订阅等\n\n"
                f"💡 提示：如在 QQ 内打开遇到问题，请复制链接到外部浏览器"
            ),
            link
        ]
