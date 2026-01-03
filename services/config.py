"""
Global configuration for the Hulaquan Service Layer.
"""
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class ServiceConfig(BaseSettings):
    """Service layer configuration."""
    
    # Enable automatic crawling in this process
    ENABLE_CRAWLER: bool = False
    
    # Database path override (optional)
    DB_PATH: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_prefix = "HLQ_"

# Global config instance
config = ServiceConfig()
