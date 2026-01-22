from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class BotAlias(SQLModel, table=True):
    """
    Bot 指令别名配置表
    存储动态配置的指令别名
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    command_key: str = Field(index=True)  # 例如 "CMD_SEARCH_EVENT"
    alias: str = Field(unique=True, index=True) # 例如 "查剧"
    is_default: bool = Field(default=False) # 标记是否为系统默认别名
    
    created_at: datetime = Field(default_factory=datetime.now)
