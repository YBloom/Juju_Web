from datetime import timedelta
import traceback, time, asyncio
from ncatbot.plugin import BasePlugin, CompatibleEnrollment, Event
from ncatbot.core import GroupMessage, PrivateMessage, BaseMessage
from .HulaquanDataManager import HulaquanDataManager
from .SaojuDataManager import SaojuDataManager
from plugins.AdminPlugin import GroupsManager, UsersManager
from ncatbot.utils.logger import get_log
bot = CompatibleEnrollment  # 兼容回调函数注册器
log = get_log()


UPDATE_LOG = [
        {"version": "0.0.1", 
         "description": "初始公测版本", 
         "date":"2025-06-28"},
        
        {"version": "0.0.2", 
         "description": "1.修改了回流票的检测逻辑（之前可能是误检测）\n2.增加了对呼啦圈学生票待开票状态的检测\n3.添加了呼啦圈未开票的票的开票定时提醒功能（提前30分钟）\n4.增加了更新日志和版本显示",
         "date": "2025-07-01"
        },
        
        {"version": "⭐0.0.3", 
         "description": """1.修改了一些缓存功能\n2.修复了一些bug\n3.添加了/hlq xx -R获取当下数据的功能
         """,
         "date": "2025-07-03"
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


class Hulaquan(BasePlugin):
    name = "Hulaquan"  # 插件名称
    version = "0.0.3"  # 插件版本
    author = "摇摇杯"  # 插件作者
    info = "与呼啦圈学生票相关的功能"  # 插件描述
    dependencies = {
        }  # 插件依赖，格式: {"插件名": "版本要求"}
    
    async def on_load(self):
        # 插件加载时执行的操作
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        self._hulaquan_announcer_task = None
        self._hulaquan_announcer_interval = 900  # 默认15分钟，可根据配置初始化
        self._hulaquan_announcer_running = False
        self.groups_manager: GroupsManager = None
        self.users_manager: UsersManager = None
        self.hlq_data_manager: HulaquanDataManager = HulaquanDataManager()
        self.saoju_data_manager: SaojuDataManager = SaojuDataManager()
        self.register_handler("AdminPlugin.pass_managers", self.get_managers)
        self.load_event = Event("Hulaquan.load_plugin", data={})
        await self._event_bus.publish_async(self.load_event)
        self.register_hulaquan_announcement_tasks()
        self.register_hlq_query()
        self.start_hulaquan_announcer(self.data["config"].get("scheduled_task_time", 600))
        
        
    async def on_close(self, *arg, **kwd):
        self.remove_scheduled_task("呼啦圈上新提醒")
        self.users_manager.is_get_managers = False
        self.stop_hulaquan_announcer()
        self.hlq_data_manager.on_close()
        self.saoju_data_manager.on_close()
        return await super().on_close(*arg, **kwd)
    
    async def _hulaquan_announcer_loop(self):
        while self._hulaquan_announcer_running:
            try:
                await self.on_hulaquan_announcer()
            except Exception as e:
                await self.on_traceback_message(f"呼啦圈定时任务异常")
            await asyncio.sleep(self._hulaquan_announcer_interval)
            
    def start_hulaquan_announcer(self, interval=None):
        if interval:
            self._hulaquan_announcer_interval = interval
        if self._hulaquan_announcer_task and not self._hulaquan_announcer_task.done():
            return  # 已经在运行
        self._hulaquan_announcer_running = True
        self._hulaquan_announcer_task = asyncio.create_task(self._hulaquan_announcer_loop())

    def stop_hulaquan_announcer(self):
        self._hulaquan_announcer_running = False
        if self._hulaquan_announcer_task:
            self._hulaquan_announcer_task.cancel()
            self._hulaquan_announcer_task = None


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
            name="切换呼啦圈上新推送模式",
            handler=self.on_switch_scheduled_check_task,
            prefix="/上新",
            description="切换呼啦圈上新推送模式",
            usage="/上新 模式编号\n2：关注呼啦圈检测的推送（定时检测一次并通知）\n1（推荐）：仅关注上新通知\n0：关闭呼啦圈上新推送\n如“/上新 1”，数字和“上新”间有空格",
            examples=["/上新"],
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
        self.data["config"]["scheduled_task_time"] = 600
        
        
        
        self.register_admin_func(
            name="保存数据（管理员）",
            handler=self.save_data_managers,
            prefix="/save",
            description="保存数据（管理员）",
            usage="/save",
            examples=["/save"],
            metadata={"category": "utility"}
        )
        
        """task_time = str(self.data['config']['scheduled_task_time'])
        self.add_scheduled_task(
            job_func=self.on_hulaquan_announcer, 
            name=f"呼啦圈上新提醒", 
            interval=task_time+"s", 
            #max_runs=10, 
            conditions=[lambda: self.data["scheduled_task_switch"]]
        )"""
        
        self.add_scheduled_task(
            job_func=self.on_schedule_save_data, 
            name=f"自动保存数据", 
            interval="1h", 
            #max_runs=10, 
        )
        

    def register_hlq_query(self):
        self.register_user_func(
            name="呼啦圈查询",
            handler=self.on_hlq_search,
            prefix="/hlq",
            description="呼啦圈查学生票余票/数量/排期",
            usage="/hlq 剧名 -I -C -R\n-I表示不显示已售罄场次，-C表示显示卡司阵容，-R表示检测此时此刻的数据，而非每15分钟自动更新的数据（但由于频繁请求容易造成请求失败或者其他问题，不建议多使用此功能），参数间需要有空格",
            # 这里的 -I 是一个可选参数，表示忽略已售罄场次
            examples=["/hlq 连璧 -I -C"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
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
            name="扫剧查询某日演出",
            handler=self.on_list_hulaquan_events_by_date,
            prefix="/date",
            description="根据日期通过呼啦圈查询当天学生票",
            usage="/date 日期 城市\n日期格式为年-月-日\n如/date 2025-06-01\n城市可以不写",
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
        self.register_pending_tickets_announcer()
        """
        {name}-{description}:使用方式 {usage}
        """
        
    async def get_managers(self, event):
        if event.data:
            self.groups_manager = event.data["managers"][1]
            self.users_manager = event.data["managers"][0]
            self.users_manager.is_get_managers = True
            print("已获取到managers")
    
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
        

    async def on_hulaquan_announcer(self, user_lists: list=[], group_lists: list=[], manual=False):
        start_time = time.time()
        try:
            result = await self.hlq_data_manager.message_update_data_async()
            is_updated = result["is_updated"]
            messages = result["messages"]
            new_pending = result["new_pending"]
            log.info("呼啦圈数据刷新成功：\n"+"\n".join(messages))
        except Exception as e:
            await self.on_traceback_message(f"呼啦圈数据更新失败")
            return False
        try:
            for user_id, user in self.users_manager.users().items():
                mode = user.get("attention_to_hulaquan")
                if (manual and user_id not in user_lists):
                    continue
                if manual or mode=="2" or (mode=="1" and is_updated):
                    for m in messages:
                        message = f"呼啦圈上新提醒：\n{m}"
                        await self.api.post_private_msg(user_id, message)
            for group_id, group in self.groups_manager.groups().items():
                mode = group.get("attention_to_hulaquan")
                if (manual and group_id not in group_lists):
                    continue
                if manual or mode=="2" or (mode=="1" and is_updated):
                    for m in messages:
                        message = f"呼啦圈上新提醒：\n{m}"
                        await self.api.post_group_msg(group_id, message)
            if new_pending:
                self.register_pending_tickets_announcer()
        except Exception as e:
            await self.on_traceback_message(f"呼啦圈上新提醒在提醒过程中失败")
            return False
        elapsed_time = time.time() - start_time
        print(f"任务执行时间: {elapsed_time}秒")
        return True
        
    def register_pending_tickets_announcer(self):
        for eid, event in self.hlq_data_manager.data["pending_events_dict"].items():
            eid = str(eid)
            if eid in self._time_task_scheduler.get_job_status(eid):
                continue
            valid_from = event.get("valid_from")
            valid_from = (valid_from - timedelta(minutes=30)) if valid_from else valid_from
            self.add_scheduled_task(
                job_func=self.on_pending_tickets_announcer,
                name=eid,
                interval=valid_from,
                kwargs={"eid":eid, "message":event.get("message")},
                max_runs=1,
            )
            
    async def on_pending_tickets_announcer(self, eid:str, message: str):
        try:
            for user_id, user in self.users_manager.users().items():
                mode = user.get("attention_to_hulaquan")
                if mode == "1" or mode == "2":
                    message = f"【即将开票】呼啦圈开票提醒：\n{message}"
                    await self.api.post_private_msg(user_id, message)
            for group_id, group in self.groups_manager.groups().items():
                mode = group.get("attention_to_hulaquan")
                if mode == "1" or mode == "2":
                    message = f"【即将开票】呼啦圈开票提醒：\n{message}"
                    await self.api.post_group_msg(group_id, message)
        except Exception as e:
            await self.on_traceback_message(f"呼啦圈开票提醒失败")
        del self.hlq_data_manager.data["pending_events_dict"][eid]
        
        
    async def on_switch_scheduled_check_task(self, msg: BaseMessage):
        user_id = msg.user_id
        group_id = None
        mode = msg.raw_message.split(" ")
        if (not len(mode)<2) and (mode[1] in ["0", "1", "2"]):
            pass
        else:
            return await msg.reply("请输入存在的模式\n用法：/上新 模式编号\n2：关注呼啦圈检测的推送（定时检测一次并通知）\n1（推荐）：仅关注上新通知\n0：关闭呼啦圈上新推送\n如“/上新 1”，数字和“上新”间有空格")
        mode = mode[1]
        if isinstance(msg, GroupMessage):
            group_id = msg.group_id
            if self.users_manager.is_op(user_id):
                self.groups_manager.switch_attention_to_hulaquan(group_id, mode)
            else:
                return await msg.reply("权限不足！需要管理员权限才能切换群聊的推送设置")
        else:
            self.users_manager.switch_attention_to_hulaquan(user_id, mode)
        if mode == "2":
            await msg.reply("已关注呼啦圈上新检测的全部推送！")
        elif mode == "1":
            await msg.reply("已关注呼啦圈的上新推送（仅上新时推送）")
        elif mode == "0":
            await msg.reply("已关闭呼啦圈上新推送。")

    async def on_hlq_search(self, msg: BaseMessage):
        # 呼啦圈查询处理函数
        args = self.extract_args(msg)
        if not args:
            await msg.reply_text("请提供剧名，例如: /hlq 连璧 -I -C -R")
            return
        event_name = args[0]
        await msg.reply_text("查询中，请稍后…")
        result = await self.hlq_data_manager.on_message_tickets_query(event_name, self.saoju_data_manager, show_cast=("-c" in args), ignore_sold_out=("-i" in args), refresh=("-r" in args))
        await msg.reply_text(result if result else "未找到相关信息，请检查剧名或网络连接。")
        

    def extract_args(self, msg):
        command = msg.raw_message.split(" ")
        args = command[1:] if len(command) > 1 else []
        for i in range(len(args)):
            args[i] = args[i].lower() # 小写处理-I -i
        return args
    
    async def on_change_schedule_hulaquan_task_interval(self, value, msg: BaseMessage):
        task_time = str(self.data['config']['scheduled_task_time'])
        if not self.users_manager.is_op(msg.user_id):
            await msg.reply_text(f"修改失败，暂无修改查询时间的权限")
        self.stop_hulaquan_announcer()
        self.start_hulaquan_announcer(interval=int(value))
        await msg.reply_text(f"已修改至{task_time}秒更新一次")
    
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
        
    async def on_list_hulaquan_events_by_date(self, msg: BaseMessage):
        # 最多有12小时数据延迟
        args = self.extract_args(msg)
        if not args:
            await msg.reply_text("【缺少日期】\n/date 日期 城市)>\n日期格式为年-月-日\n如/date 2025-06-01\n城市可以不写")
            return
        date = args[0]
        city = args[1] if len(args)>1 else None
        await msg.reply_text("查询中，请稍后…")
        result = await self.hlq_data_manager.on_message_search_event_by_date(self.saoju_data_manager, date, city)
        await msg.reply(result)
        
    async def on_hulaquan_announcer_manual(self, msg: BaseMessage):
        try:
            await self.on_hulaquan_announcer(user_lists=[msg.user_id] if isinstance(msg, PrivateMessage) else None, group_lists=[msg.group_id] if isinstance(msg, GroupMessage) else None, manual=True)
            await msg.reply_text("刷新成功")
        except Exception as e:
            print(e)
            await msg.reply_text()

    async def on_schedule_save_data(self):
        await self.save_data_managers()
        
    async def on_help(self, msg: BaseMessage):
        text = self._get_help()
        send = text["user"]
        if self.users_manager.is_op(msg.user_id):
            send += "\n以下是管理员功能："+text["admin"]
            send = "以下是用户功能：\n" + send
        await msg.reply(send)

    async def save_data_managers(self, msg=None):
        try:
            self.hlq_data_manager.save()
            self.saoju_data_manager.save()
            if msg:
                await msg.reply_text("保存成功")
            else:
                pass
                #for user_id in self.users_manager.ops_list():
                    #await self.api.post_private_msg(user_id, "自动保存成功")
        except Exception as e:
            await self.on_traceback_message(f"呼啦圈自动保存失败")
                
    async def on_traceback_message(self, context="", announce_admin=True):
        #log.error(f"呼啦圈上新提醒失败：\n" + traceback.format_exc())
        error_msg = f"{context}：\n" + traceback.format_exc()
        log.error(error_msg)
        traceback.print_exc()
        if announce_admin:
            await self.api.post_private_msg(self.users_manager.admin_id, error_msg)
