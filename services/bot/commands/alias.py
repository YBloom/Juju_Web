"""
Bot Commands Registry
集中管理 BOT 指令定义、别名映射及帮助文档
"""
from typing import List, Dict, NamedTuple, Optional

class CommandDefinition(NamedTuple):
    key: str            # 内部唯一标识 (例如 "CMD_SEARCH_EVENT")
    canonical: str      # 标准指令触发词 (例如 "/hlq")
    aliases: List[str]  # 其他触发别名列表 (例如 ["查剧", "搜剧"])
    description: str    # 用于帮助文档的描述
    hidden: bool = False # 是否在帮助菜单中隐藏

# --- 指令定义库 ---
COMMAND_REGISTRY = [
    # 帮助与基础
    CommandDefinition(
        "CMD_HELP", 
        "/help", 
        ["help", "帮助", "菜单", "/帮助", "/menu"], 
        "获取帮助文档"
    ),
    CommandDefinition(
        "CMD_LOGIN", 
        "/web", 
        ["/登录", "/login", "登录", "登陆"], 
        "获取 Web 控制台登录链接 (Magic Link)"
    ),

    # 订阅管理
    CommandDefinition(
        "CMD_SUBSCRIBE", 
        "/关注学生票", 
        ["/sub", "关注", "订阅"], 
        "关注剧目或演员的学生票提醒"
    ),
    CommandDefinition(
        "CMD_UNSUBSCRIBE", 
        "/取消关注学生票", 
        ["/unsub", "取消关注", "退订"], 
        "取消关注剧目或演员"
    ),
    CommandDefinition(
        "CMD_LIST_SUBS", 
        "/查看关注", 
        ["/list", "/我的订阅", "/订阅列表", "我的订阅", "查看关注"], 
        "查看当前已订阅的内容列表"
    ),
    CommandDefinition(
        "CMD_SET_NOTIFY", 
        "/呼啦圈通知", 
        ["/notify", "设置通知", "通知设置"], 
        "设置全局通知模式 (0-5)"
    ),

    # 演出查询
    CommandDefinition(
        "CMD_SEARCH_EVENT", 
        "/hlq", 
        ["/search", "查剧", "搜剧", "搜演出", "查票", "/query"], 
        "查询剧目信息及学生票详情"
    ),
    CommandDefinition(
        "CMD_DATE", 
        "/date", 
        ["/calendar", "查排期", "日历", "排期"], 
        "按日期查询演出排期"
    ),
    CommandDefinition(
        "CMD_COCAST", 
        "/同场演员", 
        ["/cast", "查同场", "同场", "同台"], 
        "查询多位演员的同场演出"
    ),
]



# 别名缓存 {alias: canonical_command}
_alias_cache: Dict[str, str] = {}
_cache_initialized = False

def initialize_aliases():
    """初始化别名缓存，如果数据库为空则填充默认值"""
    global _alias_cache, _cache_initialized
    from services.db.models import BotAlias
    from services.db.connection import session_scope
    from sqlmodel import select
    
    with session_scope() as session:
        # 1. 检查数据库是否已有别名
        existing_count = len(session.exec(select(BotAlias)).all())
        
        if existing_count == 0:
            # 2. 如果为空，填充默认别名
            import logging
            log = logging.getLogger(__name__)
            log.info("📢 初始化默认指令别名到数据库...")
            
            for cmd in COMMAND_REGISTRY:
                # 插入标准指令自身作为别名（虽然逻辑上可以通过 command_key 查找，但为了统一 resolve 逻辑，加入映射）
                # 这里我们保持原设计：resolve_command 负责将 别名 -> canonical
                # 我们只存额外的别名到数据库
                
                # 插入默认别名
                for alias in cmd.aliases:
                    if not session.exec(select(BotAlias).where(BotAlias.alias == alias)).first():
                        session.add(BotAlias(
                            command_key=cmd.key,
                            alias=alias,
                            is_default=True
                        ))
            session.commit()
            
        # 3. 加载所有别名到缓存
        refresh_alias_cache(session)
    
    _cache_initialized = True

def refresh_alias_cache(session=None):
    """刷新别名缓存"""
    global _alias_cache
    from services.db.models import BotAlias
    from services.db.connection import session_scope
    from sqlmodel import select
    
    setup_cache = {}
    
    # 辅助函数：通过 Key 找 Canonical
    key_to_canonical = {cmd.key: cmd.canonical for cmd in COMMAND_REGISTRY}
    
    def _do_load(sess):
        aliases = sess.exec(select(BotAlias)).all()
        for item in aliases:
            canonical = key_to_canonical.get(item.command_key)
            if canonical:
                setup_cache[item.alias.lower()] = canonical
    
    if session:
        _do_load(session)
    else:
        with session_scope() as sess:
            _do_load(sess)
            
    _alias_cache = setup_cache

def resolve_command(trigger: str) -> Optional[str]:
    """
    根据触发词解析出标准指令 (Canonical Command)。
    
    Args:
        trigger: 用户输入的指令词 (例如 "查剧")
        
    Returns:
        Canonical command (例如 "/hlq")，如果无法识别则返回 None
    """
    if not trigger:
        return None
        
    # Lazy Init
    if not _cache_initialized:
        try:
            # 尝试初始化（需要数据库连接）
            initialize_aliases()
        except Exception as e:
            # Fallback to static registry if DB fails (bootstrapping / error)
            import logging
            logging.getLogger(__name__).error(f"⚠️ Failed to init alias cache: {e}")
            return _resolve_static(trigger)
    
    trigger_lower = trigger.lower()
    
    # 1. 检查是否是标准指令本身
    for cmd in COMMAND_REGISTRY:
        if cmd.canonical.lower() == trigger_lower:
            return cmd.canonical
            
    # 2. 查缓存
    return _alias_cache.get(trigger_lower)

def _resolve_static(trigger: str) -> Optional[str]:
    """静态解析 fallback"""
    trigger_lower = trigger.lower()
    for cmd in COMMAND_REGISTRY:
        if cmd.canonical.lower() == trigger_lower:
            return cmd.canonical
        for alias in cmd.aliases:
            if alias.lower() == trigger_lower:
                return cmd.canonical
    return None

def get_command_by_key(key: str) -> Optional[CommandDefinition]:
    """根据 Key 获取指令定义"""
    for cmd in COMMAND_REGISTRY:
        if cmd.key == key:
            return cmd
    return None
