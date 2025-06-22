import os

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
        self.hlq_data_manager: HulaquanDataManager = HulaquanDataManager(file_type="json")
        self.saoju_data_manager: SaojuDataManager = SaojuDataManager(file_type="json")
        self.hlq_data_manager.on_load()
        self.saoju_data_manager.on_load()
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
            name="打开/关闭呼啦圈上新推送",
            handler=self.on_switch_scheduled_check_task,
            prefix="/上新",
            description="打开/关闭呼啦圈上新推送",
            usage="/上新",
            examples=["/上新"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )

        self.register_config(
            key="scheduled_task_time",
            default=30,
            description="自动检测呼啦圈数据更新时间",
            value_type=int,
            allowed_values=[5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60],
        )
        
        self.register_admin_func(
            name="开启/关闭呼啦圈定时查询更新数据",
            handler=self._on_switch_scheduled_check_task_for_users,
            prefix="/schedule",
            description="开启/关闭呼啦圈定时查询更新数据",
            usage="/schedule",
            examples=["/schedule"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
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
        

    def register_hlq_query(self):
        self.register_user_func(
            name="呼啦圈查询",
            handler=self.on_hlq_search,
            prefix="/hlq",
            description="呼啦圈查学生票余票/数量",
            usage="/hlq <剧名> -I\n-I表示忽略已售罄场次，去掉以显示所有场次",
            # 这里的 -I 是一个可选参数，表示忽略已售罄场次
            examples=["/hlq 连璧 -I"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )
        
        self.register_user_func(
            name="呼啦圈查询附卡司",
            handler=self.on_hlq_search_with_cast,
            prefix="/hlqc",
            description="呼啦圈查学生票余票/数量",
            usage="/hlqc <剧名> -I\n-I表示忽略已售罄场次，去掉以显示所有场次",
            examples=["/hlqc 连璧 -I"],
            tags=["呼啦圈", "学生票", "查询", "hlq"],
            metadata={"category": "utility"}
        )
        
        
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
            await msg.reply("已开启呼啦圈上新提醒功能")
        else:
            await msg.reply("已关闭呼啦圈上新提醒功能")
        
    async def on_hulaquan_announcer(self):
        is_updated, results = self.hlq_data_manager.message_update_data()
        if not is_updated:
            """订阅是否通知功能"""
            pass
        message = "\n".join(results)
        for user_id, user in self.users_manager.users().items():
            if user.get("attention_to_hulaquan"):
                await self.api.post_private_msg(user_id, message)
        for group_id, group in self.groups_manager.groups().items():
            if group.get("attention_to_hulaquan"):
                await self.api.post_group_msg(group_id, message)
    
    async def on_switch_scheduled_check_task(self, msg: BaseMessage):
        print(lambda: self.data["scheduled_task_switch"],  self.data["scheduled_task_switch"])
        user_id = msg.user_id
        group_id = None
        if isinstance(msg, GroupMessage):
            group_id = msg.group_id
            if self.users_manager.is_op(user_id):
                flag = self.groups_manager.switch_attention_to_hulaquan(group_id)
            else:
                await msg.reply("权限不足！需要管理员权限才能切换群聊的推送设置")
        else:
            flag = self.users_manager.switch_attention_to_hulaquan(user_id)
        if flag:
            await msg.reply("已关注呼啦圈上新推送！")
        else:
            await msg.reply("已关闭呼啦圈上新推送。")

    async def on_hlq_search(self, msg: BaseMessage):
        # 呼啦圈查询处理函数
        command = msg.raw_message.split(" ")
        if command[0] != "/hlq":
            return
        args = command[1:] if len(command) > 1 else []
        if not args:
            await msg.reply_text("请提供剧名，例如: /hlq 连璧")
            return
        
        event_name = args[0]
        
        await msg.reply_text("查询中，请稍后…")
        result = self.hlq_data_manager.message_tickets_query(event_name, self.saoju_data_manager, show_cast=False, ignore_sold_out=("-I" in args))
        await msg.reply_text(result if result else "未找到相关信息，请检查剧名或网络连接。")
        
    async def on_hlq_search_with_cast(self, msg: BaseMessage):
        # 呼啦圈查询处理函数，附带卡司信息
        command = msg.raw_message.split(" ")
        args = command[1:] if len(command) > 1 else []
        if not args:
            await msg.reply_text("请提供剧名，例如: /hlqc 连璧")
            return
        event_name = args[0]
        await msg.reply_text("查询中，请稍后…")
        result = self.hlq_data_manager.message_tickets_query(event_name, self.saoju_data_manager, show_cast=True, ignore_sold_out=("-I" in args))
        await msg.reply_text(result if result else "未找到相关信息，请检查剧名或网络连接。")
        