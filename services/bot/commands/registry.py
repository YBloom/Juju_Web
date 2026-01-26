import logging
from typing import Dict, Optional, Type
from services.bot.commands.base import CommandHandler, CommandContext

log = logging.getLogger(__name__)

class CommandRegistry:
    def __init__(self):
        self._handlers: Dict[str, CommandHandler] = {}

    def register(self, handler: CommandHandler):
        for trigger in handler.triggers:
            if trigger in self._handlers:
                log.warning(f"⚠️ Command '{trigger}' is already registered to {self._handlers[trigger]}. Overwriting with {handler}.")
            self._handlers[trigger] = handler

    def get_handler(self, command: str) -> Optional[CommandHandler]:
        return self._handlers.get(command)

    def get_all_handlers(self) -> list[CommandHandler]:
        return list(set(self._handlers.values()))

# Global registry instance
registry = CommandRegistry()

# Compatibility for Admin API
COMMAND_REGISTRY = [] # Value populated during registration

def register_command(cls: Type[CommandHandler]):
    """Decorator to register a command handler"""
    instance = cls()
    registry.register(instance)
    COMMAND_REGISTRY.append(instance)
    return cls

def refresh_alias_cache(session):
    """
    Refresh aliases from DB (BotAlias table).
    This allows dynamic aliases added via Admin UI to work.
    """
    try:
        from services.db.models import BotAlias
        from sqlmodel import select
        
        # 1. Clear existing dynamic aliases? 
        # The registry doesn't distinguish dynamic vs static easily unless we track them.
        # Ideally, we should reload all. But static ones are hardcoded.
        # Let's just add new ones. If we need to remove deleted ones, we might need a way to unregister.
        # For now, let's just re-register everything from DB.
        # Overwriting is allowed (with warning).
        
        aliases = session.exec(select(BotAlias)).all()
        count = 0
        
        # We need to map key -> handler instance to register alias for it.
        # Create a map first
        key_map = {cmd.key: cmd for cmd in registry.get_all_handlers()}
        
        for alias_obj in aliases:
            handler = key_map.get(alias_obj.command_key)
            if handler:
                # Register the alias pointing to this handler
                # Note: Registry.register takes a handler and uses handler.triggers.
                # Use a specific method to register alias if possible, 
                # OR we just modify the handler's triggers? 
                # Modifying triggers at runtime is risky if shared.
                # Better: Registry should map string -> handler.
                
                # Check if we need to extend Registry to support manual mapping
                registry._handlers[alias_obj.alias] = handler
                count += 1
            else:
                log.warning(f"Found alias '{alias_obj.alias}' for unknown command key '{alias_obj.command_key}'")
                
        log.info(f"🔄 [Registry] Refreshed {count} aliases from DB.")
        
    except Exception as e:
        log.error(f"❌ Failed to refresh alias cache: {e}")

