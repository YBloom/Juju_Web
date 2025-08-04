from datetime import timedelta
import traceback, time, asyncio, re
import functools
from ncatbot.plugin import BasePlugin, CompatibleEnrollment, Event
from ncatbot.core import GroupMessage, PrivateMessage, BaseMessage
from .Exceptions import RequestTimeoutException
from plugins.Hulaquan.data_managers import Saoju, Stats, Alias, Hlq, User, save_all
from plugins.Hulaquan.StatsDataManager import StatsDataManager, maxLatestReposCount
from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
from plugins.Hulaquan.AliasManager import AliasManager
from plugins.Hulaquan.HulaquanDataManager import HulaquanDataManager
from plugins.AdminPlugin.UsersManager import UsersManager
from .user_func_help import *
from .utils import parse_text_to_dict_with_mandatory_check, standardize_datetime
from ncatbot.utils.logger import get_log

bot = CompatibleEnrollment  # 兼容回调函数注册器

log = get_log()
Stats: StatsDataManager
User: UsersManager
Alias: AliasManager
Saoju: SaojuDataManager
Hlq: HulaquanDataManager



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
                Stats.on_command(command_name)
                try:
                    return await func(this, *args, **kwargs)
                except Exception as e:
                    await this.on_traceback_message(f"{command_name} 命令异常: {e}")
            return wrapper
        return decorator


class Hulaquan(BasePlugin):
    
    name = "Hulaquan"  # 插件名称
    version = "0.0.5"  # 插件版本
    author = "摇摇杯"  # 插件作者
    info = "与呼啦圈学生票相关的功能"  # 插件描述
    dependencies = {
        }  # 插件依赖，格式: {"插件名": "版本要求"}
    
    async def on_load(self):
        # 插件加载时执行的操作
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
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
            prefix="/上新",
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
        
        self.register_admin_func(
            name=HLQ_FOLLOW_TICKET_NAME,
            handler=self.on_follow_ticket,
            prefix="/关注学生票",
            description=HLQ_FOLLOW_TICKET_DESCRIPTION,
            usage=HLQ_FOLLOW_TICKET_USAGE,
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
    async def on_hulaquan_announcer(self, user_lists: list=[], group_lists: list=[], manual=False):
        start_time = time.time()
        try:
            result = await Hlq.message_update_data_async()
            if manual:
                log.info(f"updating:{Hlq.updating}, result:{len(result)}")
        except RequestTimeoutException as e:
            raise
        is_updated = result["is_updated"]
        messages = result["messages"]
        new_pending = result["new_pending"]
        if len(messages) >= 10:
            log.error(f"呼啦圈数据刷新出现异常，存在{len(messages)}条数据刷新")
            
            elapsed_time = time.time() - start_time
            if is_updated:
                print(f"任务执行时间: {elapsed_time}秒")
            return
        if is_updated:
            log.info("呼啦圈数据刷新成功：\n"+"\n".join(messages))
            if len(messages) == 2:
                messages = [messages[0]+"\n\n"+messages[1]]
        for user_id, user in User.users().items():
            mode = user.get("attention_to_hulaquan")
            if (manual and user_id not in user_lists):
                continue
            if (not mode):
                continue
            if manual or is_updated:
                if mode == "2":
                    user.switch_attention_to_hulaquan(user_id, 1)
                for m in messages:
                    message = f"呼啦圈上新提醒：\n{m}"
                    r = await self.api.post_private_msg(user_id, message)
                    if r['retcode'] == 1200:
                        User.delete_user(user_id)
        for group_id, group in User.groups().items():
            mode = group.get("attention_to_hulaquan")
            if (manual and group_id not in group_lists):
                continue
            if manual or mode=="2" or (mode=="1" and is_updated):
                for m in messages:
                    message = f"呼啦圈上新提醒：\n{m}"
                    await self.api.post_group_msg(group_id, message)
        if new_pending:
            self.register_pending_tickets_announcer()
        elapsed_time = time.time() - start_time
        if is_updated:
            print(f"任务执行时间: {elapsed_time}秒")
        return True
        
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
                valid_date = standardize_datetime(valid_date - timedelta(minutes=30))
                self.add_scheduled_task(
                    job_func=self.on_pending_tickets_announcer,
                    name=job_id,
                    interval=valid_from,
                    kwargs={"eid":eid, "message":text, "valid_from":valid_from},
                    max_runs=1,
                )
    
    @user_command_wrapper("pending_announcer")
    async def on_pending_tickets_announcer(self, eid:str, message: str, valid_from:str):
        for user_id, user in User.users().items():
            mode = user.get("attention_to_hulaquan")
            if mode == "1" or mode == "2":
                message = f"【即将开票】呼啦圈开票提醒：\n{message}"
                await self.api.post_private_msg(user_id, message)
        for group_id, group in User.groups().items():
            mode = group.get("attention_to_hulaquan")
            if mode == "1" or mode == "2":
                await self.api.post_group_msg(group_id, message)
        del Hlq.data["pending_events"][valid_from][eid]
        if len(Hlq.data["pending_events"][valid_from]) == 0:
            del Hlq.data["pending_events"][valid_from]
    
    async def on_switch_scheduled_check_task(self, msg: BaseMessage):
        user_id = msg.user_id
        group_id = None
        all_args = self.extract_args(msg)
        
        if not all_args["text_args"] or all_args.get("text_args")[0] not in ["0", "1", "2", "3"]:
            return await msg.reply("请输入存在的模式\n用法：{HLQ_SWITCH_ANNOUNCER_MODE_USAGE}")
        mode = all_args.get("text_args")[0]
        if isinstance(msg, GroupMessage):
            group_id = msg.group_id
            if User.is_op(user_id):
                User.switch_attention_to_hulaquan(group_id, mode, is_group=True)
            else:
                return await msg.reply("权限不足！需要管理员权限才能切换群聊的推送设置")
        else:
            User.switch_attention_to_hulaquan(user_id, mode)
        if mode == "2":
            await msg.reply("已关注呼啦圈的上新/补票/回流通知")
        elif mode == "1":
            await msg.reply("已关注呼啦圈的上新推送（仅上新时推送）")
        elif mode == "0":
            await msg.reply("已关闭呼啦圈上新推送。")

    @user_command_wrapper("hulaquan_search")
    async def on_hlq_search(self, msg: BaseMessage):
        # 呼啦圈查询处理函数
        all_args = self.extract_args(msg)
        if not all_args["text_args"]:
            await msg.reply_text("请提供剧名，例如: /hlq 连璧 -I -C")
            return
        event_name = all_args["text_args"][0]
        args = all_args["mode_args"]
        if "-r" in args:
            await msg.reply_text("【因数据自动刷新间隔较短，目前已不支持-R参数】")
        if isinstance(msg, PrivateMessage):
            await msg.reply_text("查询中，请稍后…")
        result = await Hlq.on_message_tickets_query(event_name, show_cast=("-c" in args), ignore_sold_out=("-i" in args), refresh=False)
        await msg.reply_text(result if result else "未找到相关信息，请尝试更换搜索名")
        

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
        messages = await Saoju.match_co_casts(casts, show_others=show_others)
        await msg.reply("\n".join(messages))
    
       
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
        result = await Hlq.on_message_search_event_by_date(date, city, ignore_sold_out=("-i" in mode_args))
        await msg.reply(result)
        
    async def on_hulaquan_announcer_manual(self, msg: BaseMessage):
        try:
            await self.on_hulaquan_announcer(user_lists=[msg.user_id] if isinstance(msg, PrivateMessage) else [], group_lists=[msg.group_id] if isinstance(msg, GroupMessage) else [], manual=True)
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
        text = self._get_help()
        send = text["user"]
        if User.is_op(msg.user_id):
            send += "\n以下是管理员功能："+text["admin"]
            send = "以下是用户功能：\n" + send
        await msg.reply(send)

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
            await msg.reply_text("用法：/alias <搜索名> <别名>")
            return
        search_name, alias = args["text_args"][0], args["text_args"][1]
        result = await self.get_eventID_by_name(search_name, msg)
        if result:
            event_id = result[0]
            Alias.add_alias(event_id, alias)
            Alias.add_search_name(event_id, search_name)
            await msg.reply_text(f"已为剧目 {result[1]} 添加别名：{alias}，对应搜索名：{search_name}")
            return
        
    async def get_eventID_by_name(self, search_name: str, msg: BaseMessage=None, msg_prefix: str="", notFoundAndRegister=False, foundInState=False):
        # return :: (event_id, event_name) or False
        result = await Hlq.search_eventID_by_name_async(search_name)
        if not result:
            if notFoundAndRegister:
                event_id = Stats.register_event(search_name)
                await msg.reply_text(msg_prefix+f"未在呼啦圈系统中找到该剧目，已为您注册此剧名以支持更多功能：{search_name}")
                return (event_id, search_name)
            if foundInState:
                if eid := Stats.get_event_id(search_name):
                    return (eid, Stats.get_event_title(eid))
            if msg:
                await msg.reply_text(msg_prefix+"未找到该剧目")
            return False
        if len(result) > 1:
            if msg:
                queue = [f"{i}. {event[1]}" for i, event in enumerate(result, start=1)]
                await msg.reply_text(msg_prefix+f"根据搜索名，找到多个匹配的剧名，请更换为唯一的搜索关键词：\n" + "\n".join(queue))
            return False
        return result[0]

    @user_command_wrapper("on_list_aliases")    
    async def on_list_aliases(self, msg: BaseMessage):
        # 直接从 AliasManager 获取别名信息
        alias_to_event = Alias.data.get("alias_to_event", {})
        event_to_names = Alias.data.get("event_to_names", {})
        events = Hlq.data.get("events", {})
        if not alias_to_event:
            await msg.reply_text("暂无别名记录。")
            return
        lines = []
        for alias, event_id in alias_to_event.items():
            event_name = events.get(event_id, {}).get("title", "未知剧目")
            search_names = ", ".join(event_to_names.get(event_id, []))
            lines.append(f"{alias}（{event_name}）: {search_names}")
        if not lines:
            await msg.reply_text("暂无别名记录。")
        else:
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
        result = await self.get_eventID_by_name(title, msg, notFoundAndRegister=True)
        event_id = result[0]
        title = result[1]
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
        event = await self.get_eventID_by_name(event_name, msg, foundInState=True)
        if not event:
            return
        event_id = event[0]
        event_title = event[1]
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
        events = Hlq.data.get("events", {})
        if not events:
            await msg.reply_text("当前无呼啦圈事件数据。")
            return
        lines = []
        index = 1
        for eid, event in events.items():
            title = event.get("title", "未知剧名")
            lines.append(f"{index}. {title}")
            index += 1
        await self.output_messages_by_pages(lines, msg, page_size=40)
            
            
    async def on_follow_ticket(self, msg: BaseMessage):
        args = self.extract_args(msg)
        if not args["text_args"]:
            return await msg.reply_text(f"请提供场次id，用法：{HLQ_FOLLOW_TICKET_USAGE}")
        ticket_id_list = args["text_args"].split(" ")
        ticket_id_list, denial = Hlq.verify_ticket_id(ticket_id_list)
        txt = ""
        if denial:
            txt += f"未找到以下场次id：{' '.join(denial)}\n"
        User.add_ticket_subscribe(ticket_id_list)
        await msg.reply_text(txt + f"已成功关注以下场次,有票务变动会提醒您：{' '.join(ticket_id_list)}")
        