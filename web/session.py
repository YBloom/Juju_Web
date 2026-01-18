from typing import Dict, Any

# Simple in-memory session store
# Key: session_id, Value: session_data dict
# TODO: Replace with Redis in production
sessions: Dict[str, Dict[str, Any]] = {}
