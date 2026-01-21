"""
Maintenance Mode Configuration Manager
维护模式配置管理

提供动态读写维护模式状态的功能，支持配置文件持久化。
优先使用配置文件，回退到环境变量。
"""
import json
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 配置文件路径（项目根目录）
CONFIG_FILE = Path(__file__).parent.parent / "maintenance.json"


def get_maintenance_mode() -> bool:
    """
    获取当前维护模式状态
    
    优先级:
    1. 配置文件 maintenance.json
    2. 环境变量 MAINTENANCE_MODE
    
    Returns:
        bool: True 表示维护模式已开启，False 表示关闭
    """
    # 1. 尝试从配置文件读取
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                enabled = data.get('enabled', False)
                logger.debug(f"Maintenance mode from config file: {enabled}")
                return bool(enabled)
        except Exception as e:
            logger.warning(f"Failed to read maintenance config file: {e}")
    
    # 2. 回退到环境变量
    mode = os.getenv("MAINTENANCE_MODE", "0").strip().lower()
    enabled = mode in {"1", "true", "yes", "on"}
    logger.debug(f"Maintenance mode from env var: {enabled}")
    return enabled


def set_maintenance_mode(enabled: bool) -> bool:
    """
    设置维护模式状态
    
    Args:
        enabled: True 开启维护模式，False 关闭
        
    Returns:
        bool: 操作是否成功
    """
    try:
        # 确保父目录存在
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入配置文件
        data = {
            "enabled": enabled,
            "updated_at": None  # 可以后续添加时间戳
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Maintenance mode set to: {enabled}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to set maintenance mode: {e}", exc_info=True)
        return False


def get_config_file_path() -> Path:
    """
    获取配置文件路径（用于调试和测试）
    
    Returns:
        Path: 配置文件的完整路径
    """
    return CONFIG_FILE
