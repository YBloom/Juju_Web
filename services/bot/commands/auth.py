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
from services.db.models import UserAuthMethod
from sqlmodel import select

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

        # FIX: Resolve real QQ ID from database
        # ctx.user_id is the internal 6-digit ID. We need the QQ number (provider_user_id) for the token.
    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        real_qq_id = ctx.user_id
        try:
            with ctx.session_maker() as session:
                stmt = select(UserAuthMethod.provider_user_id).where(
                    UserAuthMethod.user_id == ctx.user_id,
                    UserAuthMethod.provider == "qq"
                )
                auth_val = session.exec(stmt).first()
                if auth_val:
                    real_qq_id = auth_val
        except Exception:
            pass
        
        token = create_magic_link_token(real_qq_id, ctx.nickname)
        link = f"{WEB_BASE_URL}/auth/magic-link?token={token}"
        return [
            (
                f"🔐 点击下方链接登录 Web 控制台（5分钟内有效）：\n\n"
                f"✨ 登录后可查看完整演出信息、管理订阅等\n\n"
                f"💡 提示：如在 QQ 内打开遇到问题，请复制链接到外部浏览器"
            ),
            link
        ]
