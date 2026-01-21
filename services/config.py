"""
呼啦圈服务层的全局配置。
"""
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class ServiceConfig(BaseSettings):
    """服务层配置。"""
    
    # 在此进程中启用自动爬取
    ENABLE_CRAWLER: bool = False
    
    # 数据库路径覆盖（可选）
    DB_PATH: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_prefix = "HLQ_"
        extra = "ignore"  # Ignore extra fields from .env (e.g., LEGACY_COMPAT, MAINTENANCE_MODE)

# 全局配置实例
config = ServiceConfig()
