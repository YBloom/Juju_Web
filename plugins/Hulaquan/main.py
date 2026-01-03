"""Hulaquan plugin entry-point.

`Hulaquan` now retrieves its persistent state from
``services.compat.CompatContext``.  Production environments keep using the
legacy JSON ``DataManager`` singletons via :func:`get_default_context`, while
tests (and future service-backed deployments) can pass a custom context through
the plugin constructor.  The module-level ``User``, ``Alias`` … references are
updated through :func:`plugins.Hulaquan.data_managers.use_compat_context` so
command handlers keep receiving the same objects regardless of how the context
is provided.
"""

from datetime import timedelta
from typing import List
import traceback, time, asyncio, re
import functools

from ncatbot.plugin import BasePlugin, CompatibleEnrollment, Event
from ncatbot.core import GroupMessage, PrivateMessage, BaseMessage
from ncatbot.utils.logger import get_log

from services.compat import CompatContext

from .Exceptions import RequestTimeoutException
from plugins.Hulaquan.data_managers import (
    Saoju,
    Stats,
    Alias,
    Hlq,
    User,
    save_all,
    use_compat_context,
)
from plugins.Hulaquan.StatsDataManager import maxLatestReposCount
from .user_func_help import *
from .utils import parse_text_to_dict_with_mandatory_check, standardize_datetime, dateTimeToStr

from services.hulaquan.service import HulaquanService
from services.hulaquan.formatter import HulaquanFormatter
from services.hulaquan.models import TicketInfo
from services.hulaquan.tables import (
    HulaquanEvent, 
    HulaquanTicket, 
    HulaquanSubscription,
    HulaquanCast,
    TicketCastAssociation,
    HulaquanAlias
)
from services.db.connection import session_scope
from sqlmodel import select

bot = CompatibleEnrollment  # 兼容回调函数注册器

log = get_log()


def _install_context(context: Optional[CompatContext]) -> CompatContext:
    return use_compat_context(context)



UPDATE_LOG = [
        {"version": "0.0.1", 
         "description": "初始公测版本", 
         "date":"2025-06-28"},
        
        {"version": "0.0.2", 
         "description": "1.修改了回流票的检测逻辑（之前可能是误检测）\n2.增加了对呼啦圈学生票待开票状态的检测\n3.添加了呼啦圈未开票的票的开票定时提醒功能（提前30分钟）\n4.增加了更新日志和版本显示",
         "date": "2025-07-01"
        },
        
        {"version": "0.0.3", 
         "description": """1.修改了一些缓存功能\n2.修复了一些bug\n3.添加了/hlq xx -R获取当下数据的功能
         """,
         "date": "2025-07-03"
        },
        {"version": "0.0.4", 
         "description": """1./date功能实现
         """,
         "date": "2025-07-05"
        },
        {"version": "0.0.5⭐", 
         "description": """
         1.学生票repo功能
         2.区别于呼啦圈系统中存在的剧，为不存在的那些剧也声明了eventid
         """,
         "date": "2025-07-10"
        },
    ]

def get_update_log(update_log=UPDATE_LOG):
    
    # 逆序列表
    update_log.reverse()
    
    log_text = ""
    for entry in update_log:
        version = entry.get("version")
        description = entry.get("description")
        date = entry.get("date")
        log_text += f"V {version} 更新内容：\n{description}\n更新时间：{date}\n\n"
    
    return log_text.strip()


def user_command_wrapper(command_name):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(this, *args, **kwargs):
                if Stats:
                    Stats.on_command(command_name)
                try:
                    return await func(this, *args, **kwargs)
                except Exception as e:
                    # 避免循环报错：先记录日志，再尝试通知
                    log.error(f"{command_name} 命令异常: {e}")
                    import traceback
                    log.error(traceback.format_exc())
                    
                    # 使用安全的错误通知(带死循环防护)
                    try:
                        from services.system.error_protection import safe_send_error_notification
                        await safe_send_error_notification(
                            api=this.api,
                            admin_id=str(User.admin_id),
                            error=e,
                            context=f"{command_name} 命令",
                            include_traceback=True
                        )
                    except Exception as notify_error:
                        # 如果通知失败，只记录日志，不再继续
                        log.error(f"安全错误通知失败: {notify_error}")
            return wrapper
        return decorator


class Hulaquan(BasePlugin):

    name = "Hulaquan"  # 插件名称
    version = "0.0.5"  # 插件版本
    author = "摇摇杯"  # 插件作者
    info = "与呼啦圈学生票相关的功能"  # 插件描述
    dependencies = {
        }  # 插件依赖，格式: {"插件名": "版本要求"}

    def __init__(self, *args, compat_context: CompatContext | None = None, **kwargs):
        self.compat_context = compat_context or get_default_context()
        super().__init__(*args, **kwargs)
        self.hlq_service = HulaquanService()
        self.hlq_formatter = HulaquanFormatter()
    
    # Notion 配置
    # 方案 1：直接设置帮助文档的公开链接（推荐）
    NOTION_HELP_URL = "https://www.notion.so/286de516043f80c3a177ce09dda22d96"  # 帮助文档页面
    
    # 方案 2：使用 API 动态创建（需要配置父页面 ID）
    NOTION_PARENT_PAGE_ID = None  # 设置为您的 Notion 父页面 ID
    _notion_help_page_id = "286de516-043f-80c3-a177-ce09dda22d96"  # 当前帮助文档页面 ID
    
    # Notion API Token（用于自动同步）
    # ⚠️ 重要：请在环境变量中配置
    # 配置方法：
    #   Linux/Mac:  export NOTION_TOKEN=ntn_your_integration_token
    #   Windows:    $env:NOTION_TOKEN="ntn_your_integration_token"
    _notion_token = ""
    
    async def on_load(self):
        # 插件加载时执行的操作
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        
        # 启动网络健康检查
        try:
            from services.system.network_health import network_health_checker
            await network_health_checker.start_health_check()
            print("✅ 网络健康检查已启动")
        except Exception as e:
            log.warning(f"网络健康检查启动失败: {e}")
        
        # 从环境变量加载 Notion Token
        import os
        self._notion_token = self._notion_token or os.getenv('NOTION_TOKEN')
        if self._notion_token:
            print(f"✅ Notion Token 已加载（自动同步功能可用）")
        else:
            print(f"⚠️  未配置 NOTION_TOKEN（自动同步功能不可用）")
        self._hulaquan_announcer_task = None
        self._hulaquan_announcer_interval = 120
        self._hulaquan_announcer_running = False
        self.register_hulaquan_announcement_tasks()
        self.register_hlq_query()
        self.start_hulaquan_announcer(self.data["config"].get("scheduled_task_time"))
        asyncio.create_task(User.update_friends_list(self))
        
    async def on_unload(self):
        print(f"{self.name} 插件已卸载")
        
        
    async def on_close(self, *arg, **kwd):
        self.remove_scheduled_task("呼啦圈上新提醒")
        self.stop_hulaquan_announcer()
        
        # 停止网络健康检查
        try:
            from services.system.network_health import network_health_checker
            await network_health_checker.stop_health_check()
            print("✅ 网络健康检查已停止")
        except Exception as e:
            log.warning(f"网络健康检查停止失败: {e}")
        
        await self.save_data_managers(on_close=True)
        return await super().on_close(*arg, **kwd)
    
    async def _hulaquan_announcer_loop(self):
        while self._hulaquan_announcer_running:
            try:
                await self.on_hulaquan_announcer()
            except Exception as e:
                await self.on_traceback_message(f"呼啦圈定时任务异常: {e}")
            try:
                await asyncio.sleep(int(self._hulaquan_announcer_interval))
            except Exception as e:
                await self.on_traceback_message(f"定时任务sleep异常: {e}")
            
    def start_hulaquan_announcer(self, interval=None):
        if interval:
            self._hulaquan_announcer_interval = interval
        if self._hulaquan_announcer_task and not self._hulaquan_announcer_task.done():
            return  # 已经在运行
        self._hulaquan_announcer_running = True
        self._hulaquan_announcer_interval = int(self._hulaquan_announcer_interval)
        self._hulaquan_announcer_task = asyncio.create_task(self._hulaquan_announcer_loop())
        log.info("呼啦圈检测定时任务已开启")

    def stop_hulaquan_announcer(self):
        self._hulaquan_announcer_running = False
        if self._hulaquan_announcer_task:
            self._hulaquan_announcer_task.cancel()
            self._hulaquan_announcer_task = None
            log.info("呼啦圈检测定时任务已关闭")


    def register_hulaquan_announcement_tasks(self):
        if "scheduled_task_switch" not in self.data:
            self.data["scheduled_task_switch"] = False
            
        self.register_user_func(
            name="帮助",
            handler=self.on_help,
            regex=r"^(?:[/#-](?:help|帮助)|help|帮助)[\s\S]*",
            description="查看帮助",
            usage="/help",
            examples=["/help", "/help example_plugin"],
        )
        
        self.register_user_func(
            name=HLQ_SWITCH_ANNOUNCER_MODE_NAME,
            handler=self.on_switch_scheduled_check_task,
            prefix="/呼啦圈通知",
            description=HLQ_SWITCH_ANNOUNCER_MODE_DESCRIPTION,
            usage=HLQ_SWITCH_ANNOUNCER_MODE_USAGE,
            examples=["/呼啦圈通知"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )
        
        self.register_admin_func(
                    name="开启/关闭呼啦圈定时检测功能（管理员）",
                    handler=self._on_switch_scheduled_check_task_for_users,
                    prefix="/呼啦圈检测",
                    description="开启/关闭呼啦圈定时检测功能（管理员）",
                    usage="/呼啦圈检测",
                    examples=["/呼啦圈检测"],
                    metadata={"category": "utility"}
        )
        
        self.register_admin_func(
                    name="更新帮助文档（管理员）",
                    handler=self.on_sync_notion_help,
                    prefix="/update-notion",
                    description="更新帮助文档",
                    usage="/update-notion",
                    examples=["/update-notion"],
                    metadata={"category": "utility"}
        )
        
        self.register_admin_func(
                    name="调试上新通知（管理员）",
                    handler=self.on_debug_announcer,
                    prefix="/debug通知",
                    description="调试上新通知功能（管理员）",
                    usage="/debug通知 [check|user|mock]",
                    examples=["/debug通知 check", "/debug通知 user", "/debug通知 mock"],
                    metadata={"category": "debug"}
        )
        
        
        
        self.register_config(
            key="scheduled_task_time",
            default=300,
            description="自动检测呼啦圈数据更新时间",
            value_type=int,
            allowed_values=[30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600],
            on_change=self.on_change_schedule_hulaquan_task_interval,
        )
        
        self.register_admin_func(
            name="保存数据（管理员）",
            handler=self.save_data_managers,
            prefix="/save",
            description="保存数据（管理员）",
            usage="/save",
            examples=["/save"],
            metadata={"category": "utility"}
        )
        
        self.register_admin_func(
            name="广播消息（管理员）",
            handler=self.on_broadcast,
            prefix="/广播",
            description="向所有用户和群聊发送广播消息（管理员）",
            usage="/广播 <消息内容>",
            examples=["/广播 系统维护通知：今晚22:00进行更新"],
            metadata={"category": "admin"}
        )
        
        self.add_scheduled_task(
            job_func=self.on_schedule_save_data, 
            name=f"自动保存数据", 
            interval="1h", 
            #max_runs=10, 
        )
        
        self.add_scheduled_task(
            job_func=self.on_schedule_friends_list_check, 
            name=f"好友列表更新", 
            interval="1h", 
            #max_runs=10, 
        )
    
    

    def register_hlq_query(self):
        self.register_user_func(
            name=HLQ_QUERY_NAME,
            handler=self.on_hlq_search,
            prefix="/hlq",
            description=HLQ_QUERY_DESCRIPTION,
            usage=HLQ_QUERY_USAGE,
            # 这里的 -I 是一个可选参数，表示忽略已售罄场次
            examples=["/hlq 连璧 -I -C"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )

        self.register_user_func(
            name="所有呼啦圈",
            handler=self.on_list_all_hulaquan_events,
            prefix="/所有呼啦圈",
            description="列出所有呼啦圈事件",
            usage="/所有呼啦圈",
            examples=["/所有呼啦圈"],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_admin_func(
            name="呼啦圈手动刷新（管理员）",
            handler=self.on_hulaquan_announcer_manual,
            prefix="/refresh",
            description="呼啦圈手动刷新（管理员）",
            usage="/refresh",
            examples=["/refresh"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_DATE_NAME,
            handler=self.on_list_hulaquan_events_by_date,
            prefix="/date",
            description=HLQ_DATE_DESCRIPTION,
            usage=HLQ_DATE_USAGE,
            examples=["/date <日期> (城市)"],
            tags=["saoju"],
            metadata={"category": "utility"}
        )
        self.register_user_func(
            name="获取更新日志",
            handler=self.on_get_update_log,
            prefix="/版本",
            description="获取更新日志",
            usage="/版本",
            examples=["/版本"],
            tags=["version"],
            metadata={"category": "utility"}
        )
        self.register_user_func(
            name="设置剧目别名",
            handler=self.on_set_alias,
            prefix="/alias",
            description="为呼啦圈剧目设置别名，解决不同平台剧名不一致问题",
            usage="/alias <原剧名> <别名>",
            examples=["/alias lizzie 丽兹"],
            metadata={"category": "utility"}
        )
        self.register_user_func(
            name="呼啦圈别名列表",
            handler=self.on_list_aliases,
            prefix="/aliases",
            description="查看所有呼啦圈剧目别名",
            usage="/aliases",
            examples=["/aliases"],
            tags=["呼啦圈", "别名", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_NEW_REPO_NAME,
            handler=self.on_hulaquan_new_repo,
            prefix="/新建repo",
            description=HLQ_NEW_REPO_DESCRIPTION,
            usage=HLQ_NEW_REPO_USAGE,
            examples=["/新建repo"],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_GET_REPO_NAME,
            handler=self.on_hulaquan_get_repo,
            prefix="/查询repo",
            description=HLQ_GET_REPO_DESCRIPTION,
            usage=HLQ_GET_REPO_USAGE,
            examples=["/查询repo"],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_MY_REPO_NAME,
            handler=self.on_hulaquan_my_repo,
            prefix="/我的repo",
            description=HLQ_MY_REPO_DESCRIPTION,
            usage=HLQ_MY_REPO_USAGE,
            examples=["/我的repo"],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_REPORT_ERROR_NAME,
            handler=self.on_hulaquan_report_error,
            prefix="/报错repo",
            description=HLQ_REPORT_ERROR_DESCRIPTION,
            usage=HLQ_REPORT_ERROR_USAGE,
            examples=["/报错repo"],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_MODIFY_REPO_NAME,
            handler=self.on_modify_self_repo,
            prefix="/修改repo",
            description=HLQ_MODIFY_REPO_DESCRIPTION,
            usage=HLQ_MODIFY_REPO_USAGE,
            examples=["/报错repo"],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_DEL_REPO_NAME,
            handler=self.on_delete_self_repo,
            prefix="/删除repo",
            description=HLQ_DEL_REPO_DESCRIPTION,
            usage=HLQ_DEL_REPO_USAGE,
            examples=[""],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_LATEST_REPOS_NAME,
            handler=self.on_get_latest_repos,
            prefix="/最新repo",
            description=HLQ_LATEST_REPOS_DESCRIPTION,
            usage=HLQ_LATEST_REPOS_USAGE,
            examples=[""],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_QUERY_CO_CASTS_NAME,
            handler=self.on_get_co_casts,
            prefix="/同场演员",
            description=HLQ_QUERY_CO_CASTS_DESCRIPTION,
            usage=HLQ_QUERY_CO_CASTS_USAGE,
            examples=[""],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name=HLQ_FOLLOW_TICKET_NAME,
            handler=self.on_follow_ticket,
            prefix="/关注学生票",
            description=HLQ_FOLLOW_TICKET_DESCRIPTION,
            usage=HLQ_FOLLOW_TICKET_USAGE,
            examples=[""],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        self.register_user_func(
            name=HLQ_UNFOLLOW_TICKET_NAME,
            handler=self.on_unfollow_ticket,
            prefix="/取消关注学生票",
            description=HLQ_UNFOLLOW_TICKET_DESCRIPTION,
            usage=HLQ_UNFOLLOW_TICKET_USAGE,
            examples=[""],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        self.register_user_func(
            name=HLQ_VIEW_FOLLOW_NAME,
            handler=self.on_view_follow,
            prefix="/查看关注",
            description=HLQ_VIEW_FOLLOW_DESCRIPTION,
            usage=HLQ_VIEW_FOLLOW_USAGE,
            examples=[""],
            tags=["呼啦圈", "学生票", "查询"],
            metadata={"category": "utility"}
        )
        
        self.register_pending_tickets_announcer()
        """
        {name}-{description}:使用方式 {usage}
        """
    
    async def _on_switch_scheduled_check_task_for_users(self, msg: BaseMessage):
        if self._hulaquan_announcer_running:
            self.stop_hulaquan_announcer()
            await msg.reply("（管理员）已关闭呼啦圈上新检测功能")
        else:
            self.start_hulaquan_announcer()
            await msg.reply("(管理员）已开启呼啦圈上新检测功能")
            
    async def on_get_update_log(self, msg: BaseMessage):
        m = f"当前版本：{self.version}\n\n版本更新日志：\n{get_update_log()}"
        await msg.reply(m)
    
    # 呼啦圈刷新    
    @user_command_wrapper("hulaquan_announcer")
    async def on_hulaquan_announcer(self, test=False, manual=False, announce_admin_only=False):
        """
        New Service-based Announcer.
        1. Sync data from API.
        2. Filter updates based on subscriptions.
        3. Format and send.
        """
        MODE_MAP = {
            "new": 1,
            "restock": 1,
            "back": 3,
            "sold_out": 3,
            "pending": 2,
        }
        
        try:
            async with self.hlq_service as service:
                updates = await service.sync_all_data()
        except Exception as e:
            log.error(f"Announcer sync failed: {e}")
            return False

        if not updates:
            return True

        with session_scope() as session:
            # Get all user_ids that have any subscription
            stmt = select(HulaquanSubscription.user_id).distinct()
            user_ids = session.exec(stmt).all()
            
            if announce_admin_only:
                user_ids = [uid for uid in user_ids if uid == str(User.admin_id)]

            for user_id in user_ids:
                # Get user subscriptions
                stmt_s = select(HulaquanSubscription).where(HulaquanSubscription.user_id == user_id)
                subs = session.exec(stmt_s).all()
                
                user_updates = []
                for u in updates:
                    matched = False
                    required_mode = MODE_MAP.get(u.change_type, 99)
                    
                    # 1. Check global sub
                    global_sub = next((s for s in subs if s.target_type == "global"), None)
                    if global_sub and global_sub.mode >= required_mode:
                        matched = True
                    
                    # 2. Check event sub
                    if not matched:
                        event_sub = next((s for s in subs if s.target_type == "event" and s.target_id == u.event_id), None)
                        if event_sub and event_sub.mode >= required_mode:
                            matched = True
                            
                    # 3. Check ticket sub
                    if not matched:
                        ticket_sub = next((s for s in subs if s.target_type == "ticket" and s.target_id == u.ticket_id), None)
                        if ticket_sub and ticket_sub.mode >= required_mode:
                            matched = True
                    
                    # 4. Check cast (actor) sub
                    if not matched:
                        cast_subs = [s for s in subs if s.target_type == "cast"]
                        if cast_subs:
                            # Fetch ticket cast names
                            stmt_c = (
                                select(HulaquanCast.name)
                                .join(TicketCastAssociation)
                                .where(TicketCastAssociation.ticket_id == u.ticket_id)
                            )
                            ticket_casts = set(session.exec(stmt_c).all())
                            for cs in cast_subs:
                                if cs.target_id in ticket_casts and cs.mode >= required_mode:
                                    matched = True
                                    break
                    
                    if matched:
                        user_updates.append(u)
                
                if user_updates:
                    messages = self.hlq_formatter.format_updates_announcement(user_updates)
                    for m in messages:
                        is_group = user_id in User.groups()
                        if is_group:
                            await self.api.post_group_msg(user_id, m)
                        else:
                            await self.api.post_private_msg(user_id, m)
        return True

    def __generate_announce_text(self, MODE, event_id_to_ticket_ids, event_msgs, PREFIXES, categorized, tickets, user_id, user, is_group=False):
        announce = {} # event_id: {ticket_id: msg}, ...
        all_mode = int(user.get("attention_to_hulaquan", 0))
        if not is_group:
            fo_events = User.subscribe_events(user_id)
            fo_tickets = User.subscribe_tickets(user_id)
            for event in fo_events:
                eid = event['id']
                e_mode = int(event['mode'])
                if eid in event_id_to_ticket_ids:
                    announce.setdefault(eid, {})
                    for tid in event_id_to_ticket_ids[eid]:
                        ticket = tickets[tid]
                        stat = ticket['categorized']
                        if e_mode >= MODE.get(stat, 99):
                            announce[eid].setdefault(stat, set())
                            announce[eid][stat].add(tid)
            for t in fo_tickets:
                tid = t['id']
                e_mode = int(t['mode'])
                if tid in tickets.keys():
                    ticket = tickets[tid]
                    eid = ticket['event_id']
                    stat = ticket['categorized']
                    if e_mode >= MODE.get(stat, 99):
                        announce.setdefault(eid, {})
                        announce[eid].setdefault(stat, set())
                        announce[eid][stat].add(tid)
        for stat, tid_s in categorized.items():
            if all_mode >= MODE.get(stat, 99):
                for tid in tid_s:
                    ticket = tickets[tid]
                    eid = ticket['event_id']
                    stat = ticket['categorized']
                    announce.setdefault(eid, {})
                    announce[eid].setdefault(stat, set())
                    announce[eid][stat].add(tid)
        messages = []
        for eid, stats in announce.items():
            if not len(stats.keys()):
                continue
            messages.append([])
            event_prefix = event_msgs[eid]
            messages[-1].append(event_prefix)
            stats_ps = []
            for stat, t_ids in stats.items():
                t_ids = list(t_ids)
                t_ids.sort(key=int)
                stat_pfx = PREFIXES[stat]
                stats_ps.append(stat_pfx)
                t_m = [tickets[t]['message'] for t in t_ids]
                joined_messages = "\n".join(t_m)
                m = f"{stat_pfx}提醒：\n{joined_messages}"
                messages[-1].append(m)
            messages[-1][0] = f"{'|'.join(stats_ps)}提醒：\n" + messages[-1][0]
        return messages
        
    def register_pending_tickets_announcer(self):
        for valid_from, events in Hlq.data["pending_events"].items():
            if not valid_from or valid_from == "NG":
                continue
            for eid, text in events.items():
                eid = str(eid)
                job_id = f"{valid_from}_{eid}"
                _exist = self._time_task_scheduler.get_job_status(job_id)
                if _exist:
                    continue
                valid_date = standardize_datetime(valid_from, False)
                valid_date = dateTimeToStr(valid_date - timedelta(minutes=30))
                self.add_scheduled_task(
                    job_func=self.on_pending_tickets_announcer,
                    name=job_id,
                    interval=valid_from,
                    kwargs={"eid":eid, "message":text, "valid_from":valid_from},
                    max_runs=1,
                )
    
    @user_command_wrapper("pending_announcer")
    async def on_pending_tickets_announcer(self, eid:str, message: str, valid_from:str):
        message = f"【即将开票】呼啦圈开票提醒：\n{message}"
        for user_id, user in User.users().items():
            mode = user.get("attention_to_hulaquan")
            if mode == "1" or mode == "2":
                await self.api.post_private_msg(user_id, message)
        for group_id, group in User.groups().items():
            mode = group.get("attention_to_hulaquan")
            if mode == "1" or mode == "2":
                await self.api.post_group_msg(group_id, message)
        del Hlq.data["pending_events"][valid_from][eid]
        if len(Hlq.data["pending_events"][valid_from]) == 0:
            del Hlq.data["pending_events"][valid_from]
            
    @user_command_wrapper("switch_mode")
    async def on_switch_scheduled_check_task(self, msg: BaseMessage, group_switch_verify=False):
        user_id = str(msg.user_id)
        all_args = self.extract_args(msg)
        query_id = str(msg.group_id) if isinstance(msg, GroupMessage) else str(msg.user_id)
        
        # Get current global mode from DB
        async with self.hlq_service as service:
            subs = await service.get_user_subscriptions(query_id)
            global_sub = next((s for s in subs if s.target_type == "global"), None)
            current_mode = global_sub.mode if global_sub else 0
        
        # Description
        mode_desc = {
            0: "❌ 不接受通知",
            1: "🆕 只推送上新/补票",
            2: "🆕🔄 推送上新/补票/回流",
            3: "🆕🔄📊 推送上新/补票/回流/增减票"
        }
        
        # Show status if no args
        if not all_args["text_args"]:
            status_msg = [
                "📊 当前呼啦圈通知状态：",
                f"当前模式: 模式{current_mode} - {mode_desc.get(current_mode, '未知')}",
                "",
                "💡 若要设置，请使用：",
                f"{HLQ_SWITCH_ANNOUNCER_MODE_USAGE}"
            ]
            return await msg.reply("\n".join(status_msg))
        
        # Validate input
        try:
            mode = int(all_args.get("text_args")[0])
            if mode not in [0, 1, 2, 3]:
                raise ValueError()
        except (ValueError, IndexError):
            return await msg.reply(f"请输入存在的模式（0-3）\n用法：{HLQ_SWITCH_ANNOUNCER_MODE_USAGE}")
        
        # Set mode
        if isinstance(msg, GroupMessage):
            # Check OP for group settings if needed
            if group_switch_verify and User and not User.is_op(user_id):
                return await msg.reply("权限不足！需要管理员权限才能切换群聊的推送设置")
        elif mode == "0":
            await msg.reply("✅ 已设置为模式0\n已关闭呼啦圈上新推送")
            

    @user_command_wrapper("hulaquan_search")
    async def on_hlq_search(self, msg: BaseMessage):
        # 呼啦圈查询处理函数
        all_args = self.extract_args(msg)
        if not all_args["text_args"]:
            await msg.reply_text(f"请提供剧名，用法：{HLQ_QUERY_USAGE}")
            return
        event_name = all_args["text_args"][0]
        args = all_args["mode_args"]
        if "-r" in args:
            await msg.reply_text("【因数据自动刷新间隔较短，目前已不支持-R参数】")
        if isinstance(msg, PrivateMessage):
            await msg.reply_text("查询中，请稍后…")
        # Use new Service
        async with self.hlq_service as service:
            results = await service.search_events(event_name)
            if not results:
                await msg.reply_text("未找到相关信息，请尝试更换搜索名")
                return
            
            # Show top 3 events (or just 1 if exact match favored)
            for event in results[:3]:
                output = self.hlq_formatter.format_event_search_result(event, show_id=("-t" in args))
                await msg.reply_text(output)
        

    def extract_args(self, msg):
        command = [arg for arg in msg.raw_message.split(" ") if arg] 
        args = {"command":command[0], "mode_args":[arg for arg in command[1:] if arg[0] == '-'], "text_args":[arg for arg in command[1:] if arg[0] != '-']}
        for i in range(len(args["mode_args"])):
            args["mode_args"][i] = args["mode_args"][i].lower() # 小写处理-I -i
        return args
    
    async def on_change_schedule_hulaquan_task_interval(self, value, msg: BaseMessage):
        if not User.is_op(msg.user_id):
            await msg.reply_text(f"修改失败，暂无修改查询时间的权限")
            return
        self.stop_hulaquan_announcer()
        self._hulaquan_announcer_interval = int(value)
        self.start_hulaquan_announcer(interval=int(value))
        await msg.reply_text(f"已修改至{value}秒更新一次")
    
    def _get_help(self):
        """自动生成帮助文档"""
        text = {"user":"", "admin":""}
        for func in self._funcs:
            if func.permission == "user":
                text["user"] += f"👉功能描述：{func.description}\n★用法：{func.usage}\n\n"
            else:
                text["admin"] += f"👉功能描述：{func.description}\n★用法：{func.usage}\n\n"
        #for conf in self._configs:
        #    text += f"{conf.key}--{conf.description}: 类型 {conf.value_type}, 默认值 {conf.default}\n"
        return text
    
    @user_command_wrapper("query_co_casts")
    async def on_get_co_casts(self, msg: BaseMessage):
        args = self.extract_args(msg)  
        if not args["text_args"]:
            await msg.reply_text("【缺少参数】以下是/同场演员 的用法"+HLQ_QUERY_CO_CASTS_USAGE)
            return
        casts = args["text_args"]
        show_others = "-o" in args["mode_args"]
        use_hulaquan = "-h" in args["mode_args"]
        
        # Priority: Search Hulaquan DB if requested
        if use_hulaquan:
            with session_scope() as session:
                # Find tickets that have ALL requested casts
                # This needs a subquote or multiple joins. 
                # Simpler: find tickets for each cast and intersect.
                ticket_sets = []
                for cast_name in casts:
                    stmt = select(TicketCastAssociation.ticket_id).join(HulaquanCast).where(HulaquanCast.name == cast_name)
                    tids = set(session.exec(stmt).all())
                    ticket_sets.append(tids)
                
                if not ticket_sets:
                    common_tids = set()
                else:
                    common_tids = set.intersection(*ticket_sets)
                
                if not common_tids:
                    await msg.reply_text(f"❌ 在呼啦圈系统中未找到 {' '.join(casts)} 的同场演出学生票")
                    return
                
                # Fetch ticket details
                messages = [f"【呼啦圈】{' '.join(casts)} 同场演出："]
                for tid in sorted(list(common_tids)):
                    ticket = session.get(HulaquanTicket, tid)
                    if ticket:
                        # Get all casts for this ticket for display
                        stmt_casts = select(HulaquanCast.name).join(TicketCastAssociation).where(TicketCastAssociation.ticket_id == tid)
                        all_casts = session.exec(stmt_casts).all()
                        
                        info = TicketInfo(
                            id=ticket.id,
                            event_id=ticket.event_id,
                            title=ticket.title,
                            price=ticket.price,
                            stock=ticket.stock,
                            total_ticket=ticket.total_ticket,
                            status=ticket.status,
                            cast=all_casts
                        )
                        messages.append(self.hlq_formatter.format_ticket_detail(info, show_id=True))
                
                await msg.reply_text("\n".join(messages))
                return
        
        # Fallback to Saoju legacy matching
        try:
            messages = await Saoju.match_co_casts(casts, show_others=show_others)
            await msg.reply_text("\n".join(messages))
        except Exception as e:
            log.error(f"Saoju match_co_casts failed: {e}")
            await msg.reply_text("查询失败，扫剧系统可能暂时不可用。")
    
       
    @user_command_wrapper("search_by_date") 
    async def on_list_hulaquan_events_by_date(self, msg: BaseMessage):
        # 最多有12小时数据延迟
        args = self.extract_args(msg)
        if not args["text_args"]:
            await msg.reply_text("【缺少日期】以下是/date的用法\n"+HLQ_DATE_USAGE)
            return
        date = args["text_args"][0]
        city = args["text_args"][1] if len(args["text_args"])>1 else None
        mode_args = args["mode_args"]
        date_obj = standardize_datetime(date, False)
        if not date_obj:
            await msg.reply_text("【日期格式有误】以下是/date的用法\n"+HLQ_DATE_USAGE)
            return

        async with self.hlq_service as service:
            tickets = await service.get_events_by_date(date_obj, city=city)
            output = self.hlq_formatter.format_date_events(date_obj, tickets)
            await msg.reply_text(output)
        
    async def on_hulaquan_announcer_manual(self, msg: BaseMessage):
        try:
            await self.on_hulaquan_announcer(manual=True)
            await msg.reply_text("刷新成功")
        except Exception as e:
            print(e)
            await msg.reply_text()

    async def on_schedule_save_data(self):
        await self.save_data_managers()
    
    async def on_schedule_friends_list_check(self):
        await User.update_friends_list(self)
        
    @user_command_wrapper("help")
    async def on_help(self, msg: BaseMessage):
        """
        显示帮助文档
        用法：
          /help        - 发送 Notion 帮助文档链接（推荐）
          /help -t     - 显示文本格式
          /help -i     - 显示图片格式（需要 Pillow）
          /help -r     - 强制刷新缓存
          /help -n     - 强制使用 Notion 并同步
        """
        try:
            from .user_func_help import get_help_v2
            
            # 安全地解析参数
            msg_text = ""
            try:
                if hasattr(msg, 'raw_message'):
                    msg_text = msg.raw_message
                elif hasattr(msg, 'text'):
                    msg_text = msg.text
                else:
                    msg_text = str(msg)
            except Exception as e:
                log.warning(f"无法获取消息文本，使用默认模式: {e}")
                msg_text = ""
            
            text_mode = "-t" in msg_text or "--text" in msg_text
            image_mode = "-i" in msg_text or "--image" in msg_text
            force_refresh = "-r" in msg_text or "--refresh" in msg_text
            force_notion = "-n" in msg_text or "--notion" in msg_text
            
            # 优先尝试 Notion 模式（除非明确要求文本或图片）
            if not text_mode and not image_mode:
                # 尝试获取或创建 Notion 页面
                try:
                    notion_url = await self._get_or_create_notion_help(force_sync=force_notion or force_refresh)
                    if notion_url:
                        await msg.reply(
                            f"📖 呼啦圈学生票机器人 - 帮助文档\n"
                            f"🔗 点击查看完整帮助：\n{notion_url}\n\n"
                            f"💡 提示：\n"
                            f"  • 使用 /help -t 查看文本版本\n"
                            f"  • 使用 /help -i 查看图片版本\n"
                            f"  • 使用 /help -n 强制刷新 Notion"
                        )
                        return
                    else:
                        log.warning("Notion 帮助文档获取失败，回退到文本模式")
                        text_mode = True
                except Exception as e:
                    log.error(f"Notion 模式失败: {e}")
                    text_mode = True
            
            # 文本模式
            if text_mode:
                help_content = get_help_v2(force_refresh=force_refresh, as_image=False)
                await msg.reply(help_content)
                return
            
            # 图片模式
            if image_mode:
                help_image = get_help_v2(force_refresh=force_refresh, as_image=True)
                if isinstance(help_image, bytes):
                    # 成功生成图片
                    try:
                        # 保存临时文件并发送
                        import tempfile
                        import os
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                            tmp_file.write(help_image)
                            tmp_path = tmp_file.name
                        
                        try:
                            await msg.reply_image(tmp_path)
                        finally:
                            # 清理临时文件
                            try:
                                os.unlink(tmp_path)
                            except:
                                pass
                    except Exception as e:
                        log.error(f"发送帮助图片失败：{e}，回退到文本模式")
                        help_text = get_help_v2(force_refresh=force_refresh, as_image=False)
                        await msg.reply(help_text)
                else:
                    # 图片生成失败，已经返回文本
                    await msg.reply(help_image)
        
        except Exception as e:
            # 最终的安全回退：发送基本错误信息
            log.error(f"帮助命令完全失败: {e}")
            try:
                await msg.reply_text(
                    "❌ 帮助文档加载失败\n\n"
                    "请联系管理员或稍后重试。"
                )
            except:
                # 如果连错误消息都发不出去，只能放弃
                pass
    
    async def _get_or_create_notion_help(self, force_sync=False):
        """
        获取 Notion 帮助文档链接
        
        Args:
            force_sync: 是否强制重新同步（暂时忽略）
        
        Returns:
            str: Notion 页面的 URL，失败返回 None
        """
        # 方案 1：直接返回预设的 URL（最简单）
        if self.NOTION_HELP_URL:
            return self.NOTION_HELP_URL
        
        # 方案 2：尝试使用 API 创建（需要额外配置）
        if not self.NOTION_PARENT_PAGE_ID:
            log.debug("未配置 NOTION_HELP_URL 或 NOTION_PARENT_PAGE_ID")
            return None
        
        try:
            # TODO: 实现 MCP Notion API 调用
            # 这里可以调用 Notion API 创建或更新页面
            log.info("Notion API 同步功能待实现")
            return None
            
        except Exception as e:
            log.error(f"获取 Notion 帮助文档失败: {e}")
            return None

    @user_command_wrapper("auto_save")
    async def save_data_managers(self, msg=None, on_close=False):
        while Hlq.updating:
            await asyncio.sleep(0.1)
        success = await save_all(on_close)
        status = "成功" if success else "失败"
            
        log.info("🟡呼啦圈数据保存"+status)
        if msg:
            await msg.reply_text("保存"+status)
        else:
            pass
    
    @user_command_wrapper("broadcast")
    async def on_broadcast(self, msg: BaseMessage):
        """管理员广播消息到所有用户和群聊"""
        # 提取广播内容
        all_args = self.extract_args(msg)
        
        if not all_args["text_args"]:
            await msg.reply_text("❌ 请提供广播内容\n用法：/广播 <消息内容>")
            return
        
        # 组合所有文本参数作为广播内容
        broadcast_message = " ".join(all_args["text_args"])
        
        # 确认广播
        confirm_msg = [
            "📢 广播消息预览：",
            "━━━━━━━━━━━━━━━━",
            broadcast_message,
            "━━━━━━━━━━━━━━━━",
            "",
            f"将发送给：",
            f"👤 用户数：{len(User.users())}",
            f"👥 群聊数：{len(User.groups())}",
            "",
            "⚠️ 确认发送吗？请回复 '确认' 以继续"
        ]
        
        await msg.reply_text("\n".join(confirm_msg))
        
        # 等待确认（简化版，实际应该监听下一条消息）
        # 这里我们直接发送，如果需要确认机制需要额外实现
        
        # 发送广播
        await self._do_broadcast(broadcast_message, msg)
    
    async def _do_broadcast(self, message: str, original_msg: BaseMessage):
        """执行广播操作"""
        success_users = 0
        failed_users = 0
        success_groups = 0
        failed_groups = 0
        
        # 添加广播标识
        full_message = f"📢 系统广播\n━━━━━━━━━━━━━━━━\n{message}"
        
        # 向所有用户发送
        await original_msg.reply_text("📤 开始向用户发送...")
        for user_id in User.users_list():
            try:
                r = await self.api.post_private_msg(user_id, full_message)
                if r.get('retcode') == 0:
                    success_users += 1
                else:
                    failed_users += 1
                    log.warning(f"向用户 {user_id} 发送广播失败: {r.get('retcode')}")
                # 避免发送过快
                await asyncio.sleep(0.5)
            except Exception as e:
                failed_users += 1
                log.error(f"向用户 {user_id} 发送广播异常: {e}")
        
        # 向所有群聊发送
        await original_msg.reply_text("📤 开始向群聊发送...")
        for group_id in User.groups_list():
            try:
                r = await self.api.post_group_msg(group_id, full_message)
                if r.get('retcode') == 0:
                    success_groups += 1
                else:
                    failed_groups += 1
                    log.warning(f"向群聊 {group_id} 发送广播失败: {r.get('retcode')}")
                # 避免发送过快
                await asyncio.sleep(0.5)
            except Exception as e:
                failed_groups += 1
                log.error(f"向群聊 {group_id} 发送广播异常: {e}")
        
        # 发送结果统计
        result_msg = [
            "✅ 广播发送完成！",
            "",
            "📊 发送统计：",
            f"👤 用户：成功 {success_users} / 失败 {failed_users}",
            f"👥 群聊：成功 {success_groups} / 失败 {failed_groups}",
            f"📈 总成功率：{((success_users + success_groups) / (len(User.users_list()) + len(User.groups_list())) * 100):.1f}%"
        ]
        
        await original_msg.reply_text("\n".join(result_msg))
        log.info(f"📢 [广播完成] 用户:{success_users}/{len(User.users_list())}, 群聊:{success_groups}/{len(User.groups_list())}")
    
    @user_command_wrapper("sync_notion_help")
    async def on_sync_notion_help(self, msg: BaseMessage):
        """同步帮助文档到 Notion（管理员命令）"""
        if not User.is_op(msg.user_id):
            await msg.reply_text("❌ 此命令仅管理员可用")
            return
        
        if not self._notion_help_page_id:
            await msg.reply_text("❌ 未配置 Notion 页面 ID")
            return
        
        if not self._notion_token:
            error_msg = [
                "❌ 未配置 NOTION_TOKEN",
                "",
                "请按以下步骤配置：",
                "1. 创建 Notion Integration:",
                "   https://www.notion.so/my-integrations",
                "2. 获取 Internal Integration Token",
                "3. 将 Token 配置为环境变量:",
                "   Windows: $env:NOTION_TOKEN=\"ntn_xxx\"",
                "   Linux/Mac: export NOTION_TOKEN=ntn_xxx",
                "4. 重启机器人",
                "",
                "⚠️ 注意：Integration Token 需要有页面的编辑权限"
            ]
            await msg.reply_text("\n".join(error_msg))
            return
        
        await msg.reply_text("🔄 开始同步帮助文档到 Notion...")
        
        try:
            from .user_func_help import HELP_SECTIONS, HELP_DOC_VERSION, BOT_VERSION, HELP_DOC_UPDATE_DATE
            from .notion_help_manager_v2 import NotionHelpManager
            
            # 生成 Notion blocks
            mgr = NotionHelpManager()
            blocks = mgr.generate_notion_blocks(
                HELP_SECTIONS,
                {
                    'version': HELP_DOC_VERSION,
                    'bot_version': BOT_VERSION,
                    'update_date': HELP_DOC_UPDATE_DATE
                }
            )
            
            await msg.reply_text(f"✅ 生成了 {len(blocks)} 个 blocks\n⏳ 正在上传到 Notion...")
            
            # 上传到 Notion
            result = await mgr.upload_to_notion(
                page_id=self._notion_help_page_id,
                blocks=blocks,
                notion_token=self._notion_token
            )
            
            if result['success']:
                success_msg = [
                    "✅ 帮助文档同步成功！",
                    "",
                    f"📊 Blocks 数量: {result['blocks_added']}",
                    f"📄 页面 ID: {self._notion_help_page_id}",
                    f"🔗 页面链接: {self.NOTION_HELP_URL}",
                    "",
                    "💡 提示: 确保页面已设置为 'Share to web' 以便用户访问"
                ]
                await msg.reply_text("\n".join(success_msg))
                log.info(f"✅ [Notion同步成功] 上传了 {result['blocks_added']} 个 blocks")
            else:
                error_msg = [
                    "❌ 帮助文档同步失败",
                    "",
                    f"错误信息: {result['message']}",
                    f"已上传: {result['blocks_added']} blocks",
                    "",
                    "请检查:",
                    "1. NOTION_TOKEN 是否正确",
                    "2. Integration 是否有页面编辑权限",
                    "3. 页面 ID 是否正确"
                ]
                await msg.reply_text("\n".join(error_msg))
                log.error(f"❌ [Notion同步失败] {result['message']}")
            
        except Exception as e:
            error_msg = f"❌ 同步失败: {str(e)}"
            await msg.reply_text(error_msg)
            log.error(f"❌ [Notion同步失败] {e}")
            import traceback
            log.error(traceback.format_exc())
            
    @user_command_wrapper("traceback")            
    async def on_traceback_message(self, context="", announce_admin=True):
        #log.error(f"呼啦圈上新提醒失败：\n" + traceback.format_exc())
        error_msg = f"{context}：\n" + traceback.format_exc()
        log.error(error_msg)
        if announce_admin:
            await self.api.post_private_msg(User.admin_id, error_msg)
    
    @user_command_wrapper("add_alias")        
    async def on_set_alias(self, msg: BaseMessage):
        args = self.extract_args(msg)
        if len(args["text_args"]) < 2:
            await msg.reply_text("用法：/alias <剧目名> <别名>")
            return
        search_name, alias = args["text_args"][0], args["text_args"][1]
        
        async with self.hlq_service as service:
            result = await service.get_event_id_by_name(search_name)
            if result:
                event_id, event_title = result
                await service.add_alias(event_id, alias, search_name=search_name)
                await msg.reply_text(f"✅ 已为剧目 《{event_title}》 添加别名：{alias}（搜索名：{search_name}）")
            else:
                # Fallback to Stats register if not found anywhere
                if Stats:
                    event_id = Stats.register_event(search_name)
                    await service.add_alias(event_id, alias, search_name=search_name)
                    await msg.reply_text(f"⚠️ 未在数据库找到剧目，已为您注册临时项并添加别名：{alias}")
                else:
                    await msg.reply_text("❌ 未找到匹配剧目且 Stats 管理器不可用。")
        

    @user_command_wrapper("on_list_aliases")    
    async def on_list_aliases(self, msg: BaseMessage):
        async with self.hlq_service as service:
            aliases = await service.get_aliases()
            if not aliases:
                return await msg.reply_text("暂无别名记录。")
            
            # Fetch events for titles
            events = await service.get_all_events()
            id_to_title = {e.id: e.title for e in events}
            
            lines = []
            for a in aliases:
                title = id_to_title.get(a.event_id, "未知剧目")
                names = a.search_names or "无"
                lines.append(f"🔹 {a.alias} ({title}) -> 搜索名: {names}")
            
            await msg.reply_text("当前别名列表：\n" + "\n".join(lines))
    
    @user_command_wrapper("new_repo")    
    async def on_hulaquan_new_repo(self, msg: BaseMessage):
        if isinstance(msg, GroupMessage):
            if not User.is_op(msg.user_id):
                return await msg.reply_text("此功能当前仅限私聊使用。")
        
        match, mandatory_check = parse_text_to_dict_with_mandatory_check(msg.raw_message, HLQ_NEW_REPO_INPUT_DICT ,with_prefix=True)
        if mandatory_check:
            return await msg.reply_text(f"缺少以下必要字段：{' '.join(mandatory_check)}\n{HLQ_NEW_REPO_USAGE}")
        user_id = msg.user_id if not match["user_id"] else match["user_id"]
        title = match["title"]
        date = match["date"]
        seat = match["seat"]
        price = match["price"]
        content = match["content"]
        category = match["category"]
        payable = match["payable"]
        
        print(f"{user_id}上传了一份repo：剧名: {title}\n日期: {date}\n座位: {seat}\n价格: {price}\n描述: {content}\n")
        async with self.hlq_service as service:
            result = await service.get_event_id_by_name(title)
            if result:
                event_id, title = result
            else:
                event_id = Stats.register_event(title)
                await msg.reply_text(f"⚠️ 未在呼啦圈找到该剧目，已为您注册以支持更多功能：{title}")
        if not event_id:
            event_id = Stats.register_event(title) 
        report_id = Stats.new_repo(
            title=title,
            price=price,
            seat=seat,
            date=date,
            payable=payable,
            user_id=user_id,
            content=content,
            event_id=event_id,
            category=category,
        )
        await msg.reply_text(f"学生票座位记录已创建成功！\nrepoID：{report_id}\n剧名: {title}\n类型: {category}\n日期: {date}\n座位: {seat}\n实付: {price}\n原价：{payable}\n描述: {content}\n感谢您的反馈！")
        
    @user_command_wrapper("get_repo")
    async def on_hulaquan_get_repo(self, msg: BaseMessage):
        args = self.extract_args(msg)
        if not args["text_args"]:
            if "-l" in args["mode_args"]:
                messages = Stats.get_repos_list()
                await msg.reply_text("\n".join(messages))
                return
            await msg.reply_text("请提供剧名，用法："+HLQ_GET_REPO_USAGE)
            return
        event_name = args["text_args"][0]
        event_price = args["text_args"][1] if len(args["text_args"]) > 1 else None
        
        async with self.hlq_service as service:
            result = await service.get_event_id_by_name(event_name)
            if not result:
                # Fallback to Stats for legacy/manual events
                eid = Stats.get_event_id(event_name)
                if not eid:
                    await msg.reply_text(f"未找到剧目 {event_name}")
                    return
                event_id, event_title = eid, event_name
            else:
                event_id, event_title = result
        result = Stats.get_event_student_seat_repo(event_id, event_price)
        if not result:
            await msg.reply_text(f"未找到剧目 {event_title} 的学生票座位记录，快来上传吧！")
            return
        await self.output_messages_by_pages(result, msg, page_size=10)

    @user_command_wrapper("report_error_repo")
    async def on_hulaquan_report_error(self, msg: BaseMessage):
        if isinstance(msg, GroupMessage):
            return
        args = self.extract_args(msg)
        if not args["text_args"]:
            await msg.reply_text("缺少参数！\n"+HLQ_REPORT_ERROR_USAGE)
            return
        report_id = args["text_args"][0]
        error_content = " ".join(args["text_args"][1:])
        if len(error_content) > 500:
            await msg.reply_text("错误反馈内容过长，请控制在500字以内。")
            return
        # 这里可以添加将错误反馈保存到数据库或发送给管理员的逻辑
        message = Stats.report_repo_error(report_id, msg.user_id)
        await msg.reply_text(f"{message}\n感谢您的反馈，我们会尽快处理！")
    
    @user_command_wrapper("my_repo")
    async def on_hulaquan_my_repo(self, msg: BaseMessage):
        if isinstance(msg, GroupMessage):
            return
        user_id = msg.user_id
        if User.is_op(user_id):
            args = self.extract_args(msg)
            user_id = args["text_args"][0] if args["text_args"] else user_id
        repos = Stats.get_users_repo(user_id)
        if not repos:
            await msg.reply_text("您还没有提交过任何学生票座位记录。")
            return
        await self.output_messages_by_pages(repos, msg, page_size=15)
        
    @user_command_wrapper("modify_repo")
    async def on_modify_self_repo(self, msg: BaseMessage):
        if isinstance(msg, GroupMessage):
            return
        
        match, mandatory_check = parse_text_to_dict_with_mandatory_check(msg.raw_message, HLQ_MODIFY_REPO_INPUT_DICT ,with_prefix=True)
        if mandatory_check:
            return await msg.reply_text(f"缺少以下必要字段：{' '.join(mandatory_check)}")
        repoID = match["repoID"]
        date = match["date"]
        seat = match["seat"]
        price = match["price"]
        content = match["content"]
        category = match["category"]
        payable = match["payable"]
        repos = Stats.modify_repo(
            msg.user_id,
            repoID, 
            date=date, 
            seat=seat, 
            price=price, 
            content=content, 
            category=category,
            payable=payable,
            isOP=User.is_op(msg.user_id)
        )
        if not repos:
            await msg.reply_text("未找到原记录或无修改权限，请输入/我的repo查看正确的repoID")
            return
        await msg.reply_text("修改成功！现repo如下：\n"+repos[0])
    
    @user_command_wrapper("del_repo")
    async def on_delete_self_repo(self, msg: BaseMessage):
        args = self.extract_args(msg)
        if not args["text_args"]:
            await msg.reply_text("需填写要删除的repoID\n")
            return
        messages = []
        for report_id in args["text_args"]:
            repo = Stats.del_repo(report_id.strip(), msg.user_id)
            if not repo:
                messages.append(f"{report_id}删除失败！未找到对应的repo或你不是这篇repo的主人。")
            else:
                messages.append("删除成功！原repo如下：\n"+repo[0])
        await msg.reply_text("\n".join(messages))
        
    @user_command_wrapper("latest_repos")
    async def on_get_latest_repos(self, msg: BaseMessage):
        args = self.extract_args(msg)
        count = 10
        if args["text_args"]:
            if args["text_args"][0] > maxLatestReposCount:
                return await msg.reply_text(f"数字必须小于{maxLatestReposCount}")
            else:
                count = int(args["text_args"][0])
        repos = Stats.show_latest_repos(count)
        if not repos:
            await msg.reply_text("暂无数据")
            return
        await self.output_messages_by_pages(repos, msg, page_size=15)
        


    async def output_messages_by_pages(self, messages, msg: BaseMessage, page_size=10):
        # 分页输出消息
        total_pages = (len(messages) + page_size - 1) // page_size
        for i in range(total_pages):
            start = i * page_size
            end = start + page_size
            page_messages = messages[start:end]
            await msg.reply_text("\n".join(page_messages))
            
    @user_command_wrapper("list_all_events")
    async def on_list_all_hulaquan_events(self, msg: BaseMessage):
        async with self.hlq_service as service:
            events = await service.get_all_events()
            if not events:
                return await msg.reply_text("当前无呼啦圈事件数据。")
            
            lines = []
            for i, e in enumerate(events, 1):
                lines.append(f"{i}. {e.title} (ID: {e.id})")
            
            await self.output_messages_by_pages(lines, msg, page_size=40)
            
    @user_command_wrapper("follow_ticket")        
    async def on_follow_ticket(self, msg: BaseMessage):
        args = self.extract_args(msg)
        if not args["text_args"]:
            return await msg.reply_text(f"请提供场次id、剧目名或演员名，用法：\n{HLQ_FOLLOW_TICKET_USAGE}")
        
        mode_args = args["mode_args"]
        user_id = str(msg.user_id)
        target_values = {"-1", "-2", "-3"}

        # Determine mode
        setting_mode = next((item for item in mode_args if item in target_values), None)
        if not setting_mode:
            # Default to mode 1 if not specified
            setting_mode = 1
        else:
            setting_mode = int(setting_mode[1])
        
        # 0. Follow Actors (-a)
        if "-a" in mode_args:
            actor_names = args["text_args"]
            async with self.hlq_service as service:
                for actor in actor_names:
                    await service.manage_subscription(user_id, actor, "cast", mode=setting_mode)
            
            await msg.reply_text(f"✅ 已为您关注以下演员 (模式{setting_mode})：\n{' '.join(actor_names)}\n\n💡 当这些演员有新排期上架或票务变动时，系统会提醒您。")
            return
        
        # 1. Follow Tickets (-t)
        if "-t" in mode_args:
            ticket_ids = args["text_args"]
            async with self.hlq_service as service:
                for tid in ticket_ids:
                    await service.manage_subscription(user_id, tid, "ticket", mode=setting_mode)
            await msg.reply_text(f"✅ 已为您关注以下场次 (模式{setting_mode})：\n{' '.join(ticket_ids)}")
            return

        # 2. Follow Events (Default or -e)
        event_names = args["text_args"]
        followed_count = 0
        async with self.hlq_service as service:
            for e in event_names:
                result = await service.get_event_id_by_name(e)
                if result:
                    eid, _ = result
                    await service.manage_subscription(user_id, eid, "event", mode=setting_mode)
                    followed_count += 1
        
        if followed_count > 0:
            await msg.reply_text(f"✅ 已成功关注 {followed_count} 个剧目 (模式{setting_mode})，有票务变动会提醒您。")
        else:
            await msg.reply_text("未找到匹配的剧目，请尝试更精确的名称。")
    
    @user_command_wrapper("view_follow")
    async def on_view_follow(self, msg: BaseMessage):
        user_id = str(msg.user_id)
        
        async with self.hlq_service as service:
            subs = await service.get_user_subscriptions(user_id)
            
        if not subs:
            await msg.reply_text("您目前没有关注任何剧目、场次或演员。")
            return
            
        MODES = ["模式0-不接受通知", "模式1-上新/补票", "模式2-上新/补票/回流", "模式3-上新/补票/回流/增减票"]
        
        lines = []
        global_sub = next((s for s in subs if s.target_type == "global"), None)
        global_mode = global_sub.mode if global_sub else 0
        lines.append(f"您目前对剧目的通用通知设置为：\n{MODES[global_mode]}\n可通过/呼啦圈通知 模式编号修改")
        
        # Group by target type
        events = [s for s in subs if s.target_type == "event"]
        tickets = [s for s in subs if s.target_type == "ticket"]
        actors = [s for s in subs if s.target_type == "cast"]
        if events:
            lines.append("\n【关注的剧目】")
            async with self.hlq_service as service:
                for i, s in enumerate(events, 1):
                    with session_scope() as session:
                        result = session.get(HulaquanEvent, s.target_id)
                        title = result.title if result else f"未知剧目({s.target_id})"
                    lines.append(f"{i}. 《{title}》 {MODES[s.mode]}")
                    
        if actors:
            lines.append("\n【关注的演员】")
            for i, s in enumerate(actors, 1):
                lines.append(f"{i}. {s.target_id} {MODES[s.mode]}")
                
        if tickets:
            lines.append("\n【关注的场次】")
            async with self.hlq_service as service:
                for i, s in enumerate(tickets, 1):
                    with session_scope() as session:
                        result = session.get(HulaquanTicket, s.target_id)
                        if result:
                            # Create a dummy TicketInfo for formatter
                            t_info = TicketInfo(
                                id=result.id,
                                title=result.title,
                                session_time=result.session_time,
                                price=result.price,
                                stock=result.stock,
                                total_ticket=result.total_ticket,
                                status=result.status,
                                cast=[]
                            )
                            detail = self.hlq_formatter.format_ticket_detail(t_info, show_id=True)
                            lines.append(f"{i}. {detail} {MODES[s.mode]}")
                        else:
                            lines.append(f"{i}. ❌ [已过期/不存在] ID: {s.target_id}")

        await self.output_messages_by_pages(lines, msg, page_size=40)

    async def on_unfollow_ticket(self, msg: BaseMessage):
        args = self.extract_args(msg)
        if not args["text_args"]:
            return await msg.reply_text(f"请提供场次id、剧目名或演员名，用法：\n{HLQ_UNFOLLOW_TICKET_USAGE}")
        mode_args = args["mode_args"]
        user_id = str(msg.user_id)
        
        # 0. 按演员名取消关注（-a 模式）
        if "-a" in mode_args:
            actor_names = args["text_args"]
            removed = []
            async with self.hlq_service as service:
                for actor in actor_names:
                    await service.manage_subscription(user_id, actor, "cast", mode=0)
                    removed.append(actor)
            
            await msg.reply_text(f"✅ 已请求取消关注以下演员（如有）：{' '.join(removed)}")
            return
        
        # 1. 按场次ID取消关注 (-t 模式)
        if "-t" in mode_args:
            ticket_id_list = args["text_args"]
            removed = []
            async with self.hlq_service as service:
                for tid in ticket_id_list:
                    await service.manage_subscription(user_id, str(tid), "ticket", mode=0)
                    removed.append(str(tid))
            await msg.reply_text(f"✅ 已请求取消关注以下场次（如有）：{' '.join(removed)}")
            return

        # 2. 按剧目名取消关注（默认或 -e）
        event_names = args["text_args"]
        removed_events = []
        async with self.hlq_service as service:
            for e in event_names:
                result = await service.get_event_id_by_name(e)
                if result:
                    eid, _ = result
                    await service.manage_subscription(user_id, eid, "event", mode=0)
                    removed_events.append(e)
        
        if removed_events:
            await msg.reply_text(f"✅ 已请求取消关注以下剧目（如有）：\n{chr(10).join(removed_events)}")
        else:
            await msg.reply_text("未找到匹配的剧目或未处理任何取消关注。")
    
    @user_command_wrapper("debug_announcer")
    async def on_debug_announcer(self, msg: BaseMessage):
        """调试上新通知功能"""
        from plugins.Hulaquan.debug_announcer import AnnouncerDebugger
        
        args = self.extract_args(msg)
        command = args["text_args"][0] if args["text_args"] else "help"
        
        debugger = AnnouncerDebugger(self)
        
        if command == "check":
            # 检查任务状态
            info = []
            info.append("⏰ 定时任务状态：")
            info.append(f"运行状态: {'✅ 运行中' if self._hulaquan_announcer_running else '❌ 已停止'}")
            info.append(f"检测间隔: {self._hulaquan_announcer_interval} 秒")
            if self._hulaquan_announcer_task:
                info.append(f"任务完成: {'是' if self._hulaquan_announcer_task.done() else '否'}")
            await msg.reply_text("\n".join(info))
            
        elif command == "user":
            # 查看用户设置
            user_id = str(msg.user_id)
            user = User.get_user(user_id)
            if not user:
                await msg.reply_text(f"❌ 用户 {user_id} 不存在")
                return
            
            info = []
            info.append(f"👤 用户 {user_id} 的关注设置：")
            
            all_mode = user.get("attention_to_hulaquan", 0)
            mode_desc = {
                0: "❌ 不接受通知",
                1: "🆕 只推送上新/补票",
                2: "🆕🔄 上新/补票/回流",
                3: "🆕🔄📊 上新/补票/回流/增减票"
            }
            info.append(f"全局模式: {mode_desc.get(int(all_mode), '未知')}")
            
            events = User.subscribe_events(user_id)
            if events:
                info.append(f"\n📋 关注的剧目 ({len(events)}个):")
                for event in events[:5]:  # 只显示前5个
                    info.append(f"  EventID: {event['id']}, 模式: {event.get('mode', 'N/A')}")
                if len(events) > 5:
                    info.append(f"  ... 还有 {len(events)-5} 个")
            else:
                info.append("\n📋 关注的剧目: 无")
            
            tickets = User.subscribe_tickets(user_id)
            if tickets:
                info.append(f"\n🎫 关注的场次 ({len(tickets)}个):")
                for ticket in tickets[:5]:
                    info.append(f"  TicketID: {ticket['id']}, 模式: {ticket.get('mode', 'N/A')}")
                if len(tickets) > 5:
                    info.append(f"  ... 还有 {len(tickets)-5} 个")
            else:
                info.append("\n🎫 关注的场次: 无")
            
            await msg.reply_text("\n".join(info))
            
        elif command == "mock":
            # 测试模拟数据
            await msg.reply_text("🧪 开始模拟上新通知测试...")
            
            # 创建模拟数据
            mock_tickets = [
                debugger.create_mock_ticket("99001", "9001", "new", "测试剧目A", "2025-10-20", "A区1排1座", "100"),
                debugger.create_mock_ticket("99002", "9001", "new", "测试剧目A", "2025-10-21", "A区1排2座", "100"),
                debugger.create_mock_ticket("99003", "9002", "add", "测试剧目B", "2025-10-22", "B区2排1座", "150"),
                debugger.create_mock_ticket("99004", "9003", "return", "测试剧目C", "2025-10-23", "C区3排1座", "200"),
            ]
            
            mock_result = debugger.create_mock_result(mock_tickets)
            
            # 测试消息生成
            user_id = str(msg.user_id)
            messages = debugger.test_generate_announce_text(mock_result, user_id)
            
            if not messages:
                await msg.reply_text(
                    "⚠️ 没有生成任何消息！\n\n"
                    "可能的原因：\n"
                    "1. 你的全局模式为0（不接受通知）\n"
                    "2. 你没有关注相关剧目/场次\n"
                    "3. 票务变动类型不在你的关注范围内\n\n"
                    "请使用 /debug通知 user 查看你的设置"
                )
            else:
                result_info = [
                    f"✅ 成功生成 {len(messages)} 组消息",
                    f"\n模拟数据统计：",
                    f"- 上新: {len(mock_result['categorized']['new'])} 张",
                    f"- 补票: {len(mock_result['categorized']['add'])} 张",
                    f"- 回流: {len(mock_result['categorized']['return'])} 张",
                    f"\n以下是生成的消息预览："
                ]
                await msg.reply_text("\n".join(result_info))
                
                # 发送生成的消息预览
                for idx, msg_group in enumerate(messages[:2], 1):  # 只发送前2组
                    preview = "\n\n".join(msg_group)
                    await msg.reply_text(f"【消息组 #{idx}】\n{preview}")
                
                if len(messages) > 2:
                    await msg.reply_text(f"... 还有 {len(messages)-2} 组消息未显示")
        
        elif command == "log":
            # 查看最近的日志
            await msg.reply_text("📋 查看日志功能开发中...")
            
        else:
            # 帮助信息
            help_text = """
🔍 呼啦圈上新通知调试工具

可用命令：
/debug通知 check - 检查定时任务状态
/debug通知 user - 查看你的关注设置
/debug通知 mock - 使用模拟数据测试通知

调试步骤建议：
1. 先用 check 确认定时任务是否运行
2. 用 user 查看你的关注模式是否正确
3. 用 mock 测试消息生成逻辑
4. 如果 mock 没有生成消息，说明你的模式设置有问题
5. 如果 mock 能生成消息，但实际没收到，说明数据比对或发送环节有问题
"""
            await msg.reply_text(help_text)