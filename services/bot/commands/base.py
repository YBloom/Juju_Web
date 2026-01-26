from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Union, Any, Protocol

class CommandContext:
    """Command execution context"""
    def __init__(self, 
                 user_id: str, 
                 command: str, 
                 args: Dict[str, Any], 
                 nickname: str = "",
                 session_maker: Any = None,
                 service: Any = None):
        self.user_id = user_id
        self.command = command
        self.args = args  # {"text_args": [], "mode_args": []}
        self.nickname = nickname
        self.session_maker = session_maker
        self.service = service

    @property
    def text_args(self) -> List[str]:
        return self.args.get("text_args", [])

    @property
    def mode_args(self) -> List[str]:
        return self.args.get("mode_args", [])

class CommandHandler(ABC):
    """Abstract base class for command handlers"""
    
    @property
    @abstractmethod
    def triggers(self) -> List[str]:
        """List of commands that trigger this handler"""
        pass

    @abstractmethod
    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        """Execute the command"""
        pass

    @property
    def help_text(self) -> str:
        """Return help text for this command"""
        return "暂无帮助信息"

    @property
    def key(self) -> str:
        """Unique key for the command (used for DB aliases). Default to class name."""
        return self.__class__.__name__

    @property
    def canonical(self) -> str:
        """Primary trigger"""
        return self.triggers[0] if self.triggers else "unknown"

    @property
    def description(self) -> str:
        """Description for admin UI"""
        return self.help_text
