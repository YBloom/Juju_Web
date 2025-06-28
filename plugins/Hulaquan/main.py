import traceback

from ncatbot.plugin import BasePlugin, CompatibleEnrollment, Event
from ncatbot.core import GroupMessage, PrivateMessage, BaseMessage
from .HulaquanDataManager import HulaquanDataManager
from .SaojuDataManager import SaojuDataManager
from plugins.AdminPlugin import GroupsManager, UsersManager
from ncatbot.utils.logger import get_log
bot = CompatibleEnrollment  # 兼容回调函数注册器
log = get_log()

class Hulaquan(BasePlugin):
    name = "Hulaquan"  # 插件名称
    version = "0.0.1"  # 插件版本
    author = "摇摇杯"  # 插件作者
    info = "与呼啦圈学生票相关的功能"  # 插件描述
    dependencies = {
        }  # 插件依赖，格式: {"插件名": "版本要求"}

    async def on_load(self):
        # 插件加载时执行的操作
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        self.groups_manager: GroupsManager = None
        self.users_manager: UsersManager = None
        self.hlq_data_manager: HulaquanDataManager = HulaquanDataManager()
        self.saoju_data_manager: SaojuDataManager = SaojuDataManager()
        self.register_handler("AdminPlugin.pass_managers", self.get_managers)
        self.load_event = Event("Hulaquan.load_plugin", data={})
        await self._event_bus.publish_async(self.load_event)
        self.register_hulaquan_announcement_tasks()
        self.register_hlq_query()
        
        
    async def on_close(self, *arg, **kwd):
        self.remove_scheduled_task("呼啦圈上新提醒")
        self.users_manager.is_get_managers = False
        self.hlq_data_manager.on_close()
        self.saoju_data_manager.on_close()
        return await super().on_close(*arg, **kwd)

    def register_hulaquan_announcement_tasks(self):
        if "scheduled_task_switch" not in self.data:
            self.data["scheduled_task_switch"] = False
        self.register_user_func(
            name="切换呼啦圈上新推送模式",
            handler=self.on_switch_scheduled_check_task,
            prefix="/上新",
            description="切换呼啦圈上新推送模式",
            usage="/上新 (模式编号)\n2：关注呼啦圈检测的推送（定时检测一次并通知）\n1（推荐）：仅关注上新通知\n0：关闭呼啦圈上新推送",
            examples=["/上新"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )

        self.register_config(
            key="scheduled_task_time",
            default=300,
            description="自动检测呼啦圈数据更新时间",
            value_type=int,
            allowed_values=[30, 60, 120, 180, 300, 600, 900, 1800, 3600],
            on_change=self.on_change_schedule_hulaquan_task_interval,
        )
        
        self.register_admin_func(
            name="开启/关闭呼啦圈定时检测功能（管理员）",
            handler=self._on_switch_scheduled_check_task_for_users,
            prefix="/呼啦圈检测",
            description="",
            usage="/呼啦圈检测",
            examples=["/呼啦圈检测"],
            metadata={"category": "utility"}
        )
        
        self.register_admin_func(
            name="保存数据（管理员）",
            handler=self.save_data_managers,
            prefix="/save",
            description="/save",
            usage="/save",
            examples=["/save"],
            metadata={"category": "utility"}
        )
        
        task_time = str(self.data['config']['scheduled_task_time'])
        self.add_scheduled_task(
            job_func=self.on_hulaquan_announcer, 
            name=f"呼啦圈上新提醒", 
            interval=task_time+"s", 
            #max_runs=10, 
            conditions=[lambda: self.data["scheduled_task_switch"]]
        )
        
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
            usage="/hlq <剧名> (-I) (-C)\n-I表示不显示已售罄场次，-C表示显示卡司阵容",
            # 这里的 -I 是一个可选参数，表示忽略已售罄场次
            examples=["/hlq 连璧 -I -C"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )
        
        self.register_admin_func(
            name="呼啦圈手动刷新（管理员）",
            handler=self.on_hulaquan_announcer_manual,
            prefix="/refresh",
            description="/refresh",
            usage="/refresh",
            examples=["/refresh"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )
        """        self.register_user_func(
            name="呼啦圈查询附卡司",
            handler=self.on_hlq_search_with_cast,
            prefix="/hlqc",
            description="呼啦圈查学生票余票/数量/卡司",
            usage="/hlqc <剧名> -I\n-I表示忽略已售罄场次，去掉以显示所有场次",
            examples=["/hlqc 连璧 -I"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )"""
        
        self.register_user_func(
            name="扫剧查询某日演出",
            handler=self.on_saoju_search_events_by_date,
            prefix="/date",
            description="根据日期通过扫剧查询排期",
            usage="/date <日期> <城市名（可选）)>\n日期格式为年-月-日\n如/date 2025-06-01 上海",
            examples=["/date <日期> <城市名（可选）>"],
            tags=["saoju"],
            metadata={"category": "utility"}
        )
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
        flag = not self.data["scheduled_task_switch"]
        self.data["scheduled_task_switch"] = flag
        if flag:
            await msg.reply("(管理员）已开启呼啦圈上新检测功能")
        else:
            await msg.reply("（管理员）已关闭呼啦圈上新检测功能")

    async def on_hulaquan_announcer(self, user_lists: list=None, group_lists: list=None, manual=False):
        try:
            is_updated, results = self.hlq_data_manager.message_update_data()
        except Exception as e:
            print(f"呼啦圈上新提醒失败：")
            traceback.print_exc()
            return False   #message = "\n".join(results)
        try:
            for user_id, user in self.users_manager.users().items():
                mode = user.get("attention_to_hulaquan")
                if (user_lists is not None) and (user_id not in user_lists) if user_lists else False:
                    continue
                if manual or mode=="2" or (mode=="1" and is_updated):
                    for m in results:
                        message = f"呼啦圈上新提醒：\n{m}"
                        await self.api.post_private_msg(user_id, message)
                    log.info("呼啦圈数据刷新成功："+"\n".join(results))
            for group_id, group in self.groups_manager.groups().items():
                mode = group.get("attention_to_hulaquan")
                if (group_lists is not None) and (group_id not in group_lists) if group_lists else False:
                    continue
                if manual or mode=="2" or (mode=="1" and is_updated):
                    for m in results:
                        message = f"呼啦圈上新提醒：\n{m}"
                        await self.api.post_group_msg(group_id, message)
            return True
        except Exception as e:
            print(f"呼啦圈上新提醒失败：")
            traceback.print_exc()
            return False #message = "\n".join(results)
 

    async def on_switch_scheduled_check_task(self, msg: BaseMessage):
        #print(lambda: self.data["scheduled_task_switch"],  self.data["scheduled_task_switch"])
        user_id = msg.user_id
        group_id = None
        mode = msg.raw_message.split(" ")
        if (not len(mode)<2) and (mode[1] in ["0", "1", "2"]):
            pass
        else:
            return await msg.reply("请输入存在的模式：\n2：关注呼啦圈检测的推送（每30秒检测一次并通知）\n1（推荐）：仅关注上新通知\n0：关闭呼啦圈上新推送")
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
            await msg.reply_text("请提供剧名，例如: /hlq 连璧 -I -C")
            return
        event_name = args[0]
        await msg.reply_text("查询中，请稍后…")
        result = self.hlq_data_manager.on_message_tickets_query(event_name, self.saoju_data_manager, show_cast=("-c" in args), ignore_sold_out=("-i" in args))
        await msg.reply_text(result if result else "未找到相关信息，请检查剧名或网络连接。")
        

    def extract_args(self, msg):
        command = msg.raw_message.split(" ")
        args = command[1:] if len(command) > 1 else []
        for i in range(len(args)):
            args[i] = args[i].lower() # 小写处理-I -i
        return args
    
    async def on_change_schedule_hulaquan_task_interval(self, msg: BaseMessage):
        task_time = str(self.data['config']['scheduled_task_time'])
        if not msg.user_id in self.users_manager.ops_list():
            await msg.reply_text(f"修改失败，暂无修改查询时间的权限")
        self.remove_scheduled_task("呼啦圈上新提醒")
        self.add_scheduled_task(
            job_func=self.on_hulaquan_announcer, 
            name=f"呼啦圈上新提醒", 
            interval=task_time+"s", 
            #max_runs=10, 
            conditions=[lambda: self.data["scheduled_task_switch"]]
        )
        await msg.reply_text(f"已修改至{task_time}秒更新一次")
    

        
    async def on_saoju_search_events_by_date(self, msg: BaseMessage):
        # 最多有12小时数据延迟
        args = self.extract_args(msg)
        if not args:
            await msg.reply_text("【缺少日期】\n/date <日期> <城市名（可选）)>\n日期格式为年-月-日\n如/date 2025-06-01 上海")
            return
        date = args[0]
        city = args[1] if len(args)>1 else None
        await msg.reply_text("查询中，请稍后…")
        result = self.saoju_data_manager.on_search_event_by_date(date, city)
        await msg.reply(result)
        
    async def on_hulaquan_announcer_manual(self, msg: BaseMessage):
        try:
            await self.on_hulaquan_announcer(user_lists=[msg.user_id] if isinstance(msg, PrivateMessage) else None, group_lists=[msg.group_id] if isinstance(msg, GroupMessage) else None, manual=True)
            await msg.reply_text("刷新成功")
        except Exception as e:
            print(e)
            await msg.reply_text("刷新失败")

    async def on_schedule_save_data(self):
        await self.save_data_managers()

    async def save_data_managers(self, msg=None):
        try:
            self.hlq_data_manager.save()
            self.saoju_data_manager.save()
            if msg:
                await msg.reply_text("保存成功")
            else:
                for user_id in self.users_manager.ops_list():
                    await self.api.post_private_msg(user_id, "自动保存成功")
        except Exception as e:
            if msg:
                await msg.reply_text(f"保存失败，原因是{e}")
