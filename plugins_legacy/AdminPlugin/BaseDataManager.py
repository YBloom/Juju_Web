"""Backward compatibility re-export.

The canonical BaseDataManager now lives in services.common.base_data_manager.
This module re-exports it so existing code that imports from here continues to work.
"""
from services.common.base_data_manager import BaseDataManager

__all__ = ["BaseDataManager"]
