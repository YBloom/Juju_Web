from datetime import datetime
from plugins.AdminPlugin.BaseDataManager import BaseDataManager
from ncatbot.plugin import BasePlugin
from ncatbot.utils.logger import get_log
from copy import deepcopy
log = get_log()


class UsersManager(BaseDataManager):
    
    admin_id = "3022402752"

    def __init__(self, file_path=None):
        super().__init__(file_path=file_path)


    def on_load(self, data=None):
        first_init = False
        if data:
            first_init = True
            self.data["users"] = data["users"]
            self.data["users_list"] = data["users_list"]
            self.data["ops_list"] = data["ops_list"]
            self.data["groups"] = data["groups"]
            self.data["groups_list"] = data["groups_list"]
            print(len(self.data["users_list"]))
            return super().on_load()
        if "users" not in self.data:
            self.data["users"] = data["users"] if first_init else {}
        if "users_list" not in self.data:
            self.data["users_list"] = data["users_list"] if first_init else []
        if "ops_list" not in self.data:
            self.data["ops_list"] = data["ops_list"] if first_init else []
        if "groups" not in self.data:
            self.data["groups"] = data["groups"] if first_init else {}
        if "groups_list" not in self.data:
            self.data["groups_list"] = data["groups_list"] if first_init else []
        self.data.setdefault("todays_likes", [])
        return super().on_load()
        
    def users(self):
        return deepcopy(self.data.get("users", {}))
        
    def users_list(self):
        return deepcopy(self.data.get("users_list", []))
    
    def ops_list(self):
        return self.data.get("ops_list", [])
    
    def groups(self):
        return deepcopy(self.data.get("groups", {}))
        
    def groups_list(self):
        return deepcopy(self.data.get("groups_list", []))
        
    def add_group(self, group_id):
        if not isinstance(group_id, str):
            group_id = str(group_id)
        if group_id in self.data["groups_list"]:
            return
        self.data["groups_list"].append(group_id)
        self.data["groups"][group_id] = {
            "activate": True,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "attention_to_hulaquan": 0,
        }
    
    def delete_group(self, group_id):
        if not isinstance(group_id, str):
            group_id = str(group_id)
        if group_id in self.data["groups_list"]:
            self.data["groups_list"].remove(group_id)
            del self.data["groups"][group_id]
        
    def add_user(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id in self.data["users_list"]:
            return
        self.data["users_list"].append(user_id)
        self.data["users"][user_id] = {
            "activate": True,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "attention_to_hulaquan": 1,
            "chats_count":0,

            # 订阅权限
            "subscribe": {
                "is_subscribe": False,
                "subscribe_time": None,
                "subscribe_tickets": [],
            }
        }
        
    def add_chats_count(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if "chats_count" not in self.data['users'][user_id]:
            self.data["users"][user_id]["chats_count"] = 0
        self.data["users"][user_id]["chats_count"] += 1
        return self.data["users"][user_id]
    
    def delete_user(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id in self.data["users_list"]:
            self.data["users_list"].remove(user_id)
            del self.data["users"][user_id]
            
    def add_op(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id in self.data["ops_list"]:
            
            return False
        if user_id not in self.data["users_list"]:
            self.add_user(user_id)
        self.data["ops_list"].append(user_id)
        self.data["users"][user_id]["is_op"] = True
        return True
        
    def de_op(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id in self.data["ops_list"]:
            self.data["ops_list"].remove(user_id)
            self.data["users"][user_id]["is_op"] = False
            return True
        return False
            
    def is_op(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id in self.data["ops_list"]:
            return True
        return False
    
    def switch_attention_to_hulaquan(self, user_id, mode=0, is_group=False):
        # mode = 0: 取消推送，mode = 1: 关注更新，mode = 2：关注一切推送（更新或无更新）
        if not isinstance(user_id, str):
            user_id = str(user_id)
        key = "users" if not is_group else "groups"
        try:
            self.data[key][user_id]["attention_to_hulaquan"] = mode
        except KeyError:
            if key == "users":
                self.add_user(user_id)
            else:
                self.add_group(user_id)
            self.data[key][user_id]["attention_to_hulaquan"] = mode
        return mode
    
    def new_subscribe(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id not in self.data["users_list"]:
            self.add_user(user_id)
        self.data["users"][user_id]["subscribe"]["is_subscribe"] = True
        self.data["users"][user_id]["subscribe"]["subscribe_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "subscribe_tickets" not in self.data["users"][user_id]["subscribe"]:
            self.data["users"][user_id]["subscribe"]["subscribe_tickets"] = []
        return True
   
    def add_ticket_subscribe(self, user_id, ticket_id):
        if not isinstance(user_id, str):
           user_id = str(user_id)
        if user_id not in self.users_list():
            self.add_user(user_id)
        if isinstance(ticket_id, int) or isinstance(ticket_id, str):
            ticket_id = [ticket_id]
        for i in ticket_id:
            self.data["users"][user_id]["subscribe"]["subscribe_tickets"].append(str(i))
        return True
    
    async def post_private_msg(self, bot: BasePlugin, user_id, text, condition=True):
        if not condition:
            return False
        else:
            return await bot.api.post_private_msg(user_id, text)
   
    async def send_likes(self, bot: BasePlugin):
        date = datetime.now().strftime("%Y-%m-%d")
        if date in self.data["todays_likes"]:
            return False
        for i in self.users_list():
            await bot.api.send_like(i, 10)
        self.data["todays_likes"].append(date)
        return True
    
    async def check_friend_status(self, bot: BasePlugin):
        result = await bot.api.get_friend_list(False)
        
        friends = [str(i["user_id"]) for i in result["data"]]
        for user_id in self.users_list():
            if user_id not in friends:
                r = await bot.api.post_private_msg(user_id, text="老师请添加bot为好友，防止消息被误吞~")
                if r['retcode'] == 1200 and not r['data']:
                        self.delete_user(user_id)
            else:
                self.add_user(user_id)
    
    async def update_friends_list(self, bot: BasePlugin):
        await self.check_friend_status(bot)
        return await self.send_likes(bot)
