from .base import CommandHandler, CommandContext
from .registry import registry, register_command, COMMAND_REGISTRY, refresh_alias_cache

# Import submodules to trigger registration
from . import query, notify, feedback, auth, help

# Optional: expose legacy resolve_command if strictly needed for other modules
# But we should rely on registry.

def resolve_command_legacy(trigger: str) -> str:
    """Legacy alias resolution helper if needed externally"""
    handler = registry.get_handler(trigger)
    if handler:
        # Since we don't have a single 'canonical' string in handler (it has list of triggers),
        # this legacy function is tricky. 
        # But honestly, external callers should use registry.get_handler directly.
        pass
    return None

__all__ = ["CommandHandler", "CommandContext", "registry", "register_command", "COMMAND_REGISTRY", "refresh_alias_cache"]
