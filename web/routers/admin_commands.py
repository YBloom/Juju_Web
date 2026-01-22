from fastapi import APIRouter, Cookie, HTTPException, Body
from services.db.connection import session_scope
from services.db.models import BotAlias
from services.bot.commands import COMMAND_REGISTRY, refresh_alias_cache
from web.routers.admin_utils import verify_admin_session, ADMIN_COOKIE_NAME
from sqlmodel import select
from pydantic import BaseModel
from typing import List

router = APIRouter(tags=["Admin API"])

# Pydantic Models
class AliasCreate(BaseModel):
    command_key: str
    alias: str

class AliasResponse(BaseModel):
    id: int
    command_key: str
    alias: str
    is_default: bool
    
class CommandInfo(BaseModel):
    key: str
    canonical: str
    description: str
    aliases: List[AliasResponse]

@router.get("/commands", response_model=List[CommandInfo])
async def get_commands(admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """获取所有指令及其当前别名"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        # 获取所有别名数据
        db_aliases = session.exec(select(BotAlias)).all()
        
        # 按 command_key 分组
        alias_map = {}
        for item in db_aliases:
            if item.command_key not in alias_map:
                alias_map[item.command_key] = []
            alias_map[item.command_key].append(AliasResponse(
                id=item.id,
                command_key=item.command_key,
                alias=item.alias,
                is_default=item.is_default
            ))
            
        # 构建返回列表
        result = []
        for cmd in COMMAND_REGISTRY:
            result.append(CommandInfo(
                key=cmd.key,
                canonical=cmd.canonical,
                description=cmd.description,
                aliases=alias_map.get(cmd.key, [])
            ))
            
        return result

@router.post("/aliases", response_model=AliasResponse)
async def create_alias(item: AliasCreate, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """创建新别名"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    valid_keys = [cmd.key for cmd in COMMAND_REGISTRY]
    if item.command_key not in valid_keys:
        raise HTTPException(status_code=400, detail="Invalid command key")
        
    if not item.alias or len(item.alias.strip()) == 0:
        raise HTTPException(status_code=400, detail="Alias cannot be empty")
        
    normalized_alias = item.alias.strip()

    with session_scope() as session:
        # 检查重复
        existing = session.exec(select(BotAlias).where(BotAlias.alias == normalized_alias)).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Alias '{normalized_alias}' already exists")
            
        new_alias = BotAlias(
            command_key=item.command_key,
            alias=normalized_alias,
            is_default=False
        )
        session.add(new_alias)
        session.commit()
        session.refresh(new_alias)
        
        # 刷新缓存
        refresh_alias_cache(session)
        
        return AliasResponse(
            id=new_alias.id,
            command_key=new_alias.command_key,
            alias=new_alias.alias,
            is_default=new_alias.is_default
        )

@router.delete("/aliases/{alias_id}")
async def delete_alias(alias_id: int, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """删除别名"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        alias = session.get(BotAlias, alias_id)
        if not alias:
            raise HTTPException(status_code=404, detail="Alias not found")
            
        # 可选：禁止删除默认别名？目前允许删除，因为默认别名也是在初始化时插入的
        # 但如果允许删除默认别名，用户可能会误删常用词
        # 策略：is_default 为 True 的，给予警告或禁止？
        # 用户需求可以删除所有，这里暂不限制，但前端可以做提示
        
        session.delete(alias)
        session.commit()
        
        # 刷新缓存
        refresh_alias_cache(session)
        
    return {"status": "ok"}
