"""
BotHandler - QQ Bot 命令处理 (Refactored Phase 2)
"""
import logging
import asyncio
from typing import Optional, List, Dict, Union

from services.hulaquan.service import HulaquanService
from services.db.connection import session_scope
from services.db.models import User, UserAuthMethod
from services.bot.commands import registry, CommandContext
from sqlmodel import select

log = logging.getLogger(__name__)

ROOT_ID = "3022402752"

def extract_args(message: str) -> Dict:
    """
    解析命令参数
    返回: {"command": str, "text_args": List[str], "mode_args": List[str]}
    """
    parts = [p for p in message.split() if p]
    if not parts:
        return {"command": "", "text_args": [], "mode_args": []}
    
    # 直接使用原始触发词，由 Registry 处理别名匹配
    raw_trigger = parts[0]
    
    # 模式参数：以 - 开头且后面不是纯数字的 (如 -E, -A, -all)
    # 文本参数：不以 - 开头，或者是类似 -3 这样的负数形式（用于指定级别或通过价格）
    mode_args = [p.lower() for p in parts[1:] if p.startswith("-") and not p[1:].isdigit()]
    text_args = [p for p in parts[1:] if not p.startswith("-") or p[1:].isdigit()]
    
    return {"command": raw_trigger, "text_args": text_args, "mode_args": mode_args}


class BotHandler:
    def __init__(self, service: HulaquanService):
        self.service = service
        # Ensure commands are loaded (imported in services/bot/commands/__init__.py)

    async def _ensure_user_exists(self, user_id: str, nickname: str = ""):
        """确保用户在数据库中存在 (由于外键约束)"""
        try:
            with session_scope() as session:
                user = session.get(User, user_id)
                if not user:
                    # 只有 group_ 这种自定义 ID 才会在这里创建
                    # 正常用户应该在 resolve_user_id 中创建
                    user = User(user_id=user_id, nickname=nickname or user_id)
                    session.add(user)
                    session.commit()
                    log.info(f"👤 [用户] 已为 {user_id} 创建新用户记录")
                elif nickname and user.nickname != nickname:
                    # 顺便更新一下昵称
                    user.nickname = nickname
                    session.add(user)
                    session.commit()
        except Exception as e:
            log.error(f"❌ [用户] 确保用户 {user_id} 存在时出错: {e}")

    async def resolve_user_id(self, qq_id: str, nickname: str = "") -> str:
        """
        解析 QQ ID 到标准化的 6 位 User ID。
        1. 检查 UserAuthMethod 是否已存在映射。
        2. 如果不存在，自动创建一个 6 位 User ID 并建立映射。
        3. 始终返回 6 位数字 ID。
        """
        # 如果已经是 6 位数字 ID 或 Group ID，直接返回
        if qq_id.startswith("group_") or (len(qq_id) == 6 and qq_id.isdigit() and qq_id.startswith("0")):
             return qq_id

        try:
            with session_scope() as session:
                # 1. 查找是否存在映射
                stmt = select(UserAuthMethod).where(
                    UserAuthMethod.provider == "qq",
                    UserAuthMethod.provider_user_id == qq_id
                )
                auth = session.exec(stmt).first()
                if auth:
                    return auth.user_id
                
                # 2. 不存在映射，自动创建 standardized user
                # 检查是否此前有人直接把 QQ 号当成了 user_id (兼容历史数据，直到后续迁移脚本完成)
                legacy_user = session.get(User, qq_id)
                
                new_user_id = User.generate_next_id(session)
                log.info(f"✨ [Auth] Auto-registering new standardization for QQ {qq_id} -> User {new_user_id}")
                
                new_user = User(user_id=new_user_id, nickname=nickname or f"QQ用户_{qq_id[-4:]}")
                session.add(new_user)
                
                new_auth = UserAuthMethod(
                    user_id=new_user_id,
                    provider="qq",
                    provider_user_id=qq_id,
                    is_primary=True
                )
                session.add(new_auth)
                session.commit()
                
                return new_user_id
                
        except Exception as e:
             log.error(f"❌ [Auth] Failed to resolve or create user for {qq_id}: {e}")
             # Fallback
             return qq_id

    async def handle_message(self, message: str, user_id: str, nickname: str = "") -> Optional[Union[str, List[str]]]:
        return await self.handle_group_message(0, int(user_id), message, nickname=nickname)

    async def handle_group_message(self, group_id: int, user_id: int, message: str, sender_role: str = "member", nickname: str = "") -> Optional[Union[str, List[str]]]:
        msg = message.strip()
        uid_str = str(user_id)
        
        # log.info(f"💬 [消息] 收到来自 {user_id} 的消息: {msg}")
        
        args = extract_args(msg)
        command_trigger = args["command"]
        
        # 1. 查找 Handler
        handler = registry.get_handler(command_trigger)
        if not handler:
            return None
        
        log.info(f"🤖 [Bot] Dispatching '{command_trigger}' to {handler.__class__.__name__}")

        # 2. 权限与身份解析
        is_root = str(user_id) == ROOT_ID
        if is_root and group_id != 0:
            effective_uid = f"group_{group_id}"
            await self._ensure_user_exists(effective_uid, nickname=f"群组 {group_id}")
        else:
            effective_uid = await self.resolve_user_id(uid_str, nickname=nickname)
            if effective_uid.startswith("group_"):
                # 虽然一般 resolve_user_id 不会返回 group_，除非数据库本来就有脏数据
                await self._ensure_user_exists(effective_uid, nickname=nickname)

        # 3. 构建上下文
        ctx = CommandContext(
            user_id=effective_uid,
            command=command_trigger,
            args=args,
            nickname=nickname,
            session_maker=session_scope,
            service=self.service
        )

        # 4. 执行命令
        try:
            response = await handler.handle(ctx)
            
            # 群组消息特殊处理 (添加前缀等)
            # 注意：某些命令返回 List[str] 或 Tuple (auth link)，这时候 replace 会报错
            # 我们需要检查类型
            if effective_uid.startswith("group_"):
                if isinstance(response, str):
                    response = response.replace("✅ ", f"✅ [群订阅] ")
                # 如果是 List，通常是图文混排或其他复杂消息，暂时不自动加前缀以免破坏格式
            
            return response
            
        except Exception as e:
            log.exception(f"❌ [Bot] Error handling command '{command_trigger}': {e}")
            return "❌ 系统内部错误，请稍后重试。"
