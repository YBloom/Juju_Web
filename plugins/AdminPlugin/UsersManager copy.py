from datetime import datetime
from . import BaseDataManager
from pathlib import Path
from ncatbot.utils.logger import get_log
log = get_log()

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.activate = True
        self.create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.attention_to_hulaquan = 1
        self.chats_count = 0
        self.is_op = False
        self.subscribe = {
            "is_subscribe": False,
            "subscribe_time": None,
            "subscribe_tickets": [],
        }
    
    def __repr__(self):
        return f"User(user_id={self.user_id}, activate={self.activate}, create_time={self.create_time}, attention_to_hulaquan={self.attention_to_hulaquan}, chats_count={self.chats_count}, subscribe={self.subscribe})"

    def __getitem__(self, item):
        return getattr(self, item, None)
    
    def __setitem__(self, key, value):
        setattr(self, key, value)


class UsersManager(BaseDataManager):
    
    admin_id = "3022402752"
    
    def __init__(self, data=None):
        super().__init__(self.file_path)
        first_init = False
        if (not self.data) and data:
            first_init = True
        # self.is_get_managers = False #插件Hulaquan有没有捕获managers
        self.user_objs = {}
        if "users" not in self.data:
            self.data["users"] = data["users"] if first_init else {}
        if "users_list" not in self.data:
            self.data["users_list"] = data["users_list"] if first_init else []
        if "ops_list" not in self.data:
            self.data["ops_list"] = data["ops_list"] if first_init else []
        
        
    def users(self):
        return self.data.get("users", {})
        
    def users_list(self):
        return self.data.get("users_list", [])
    
    def ops_list(self):
        return self.data.get("ops_list", [])
    
    def transferUserObjs(self, user: User):
        return user.__dict__
        
        
    def add_user(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id in self.data["users_list"]:
            return
        user = User(user_id)
        self.data["users_list"].append(user_id)
        self.data["users"][user_id] = user.__dict__
        
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
    
    def switch_attention_to_hulaquan(self, user_id, mode=0):
        # mode = 0: 取消推送，mode = 1: 关注更新，mode = 2：关注一切推送（更新或无更新）
        if not isinstance(user_id, str):
            user_id = str(user_id)
        try:
            self.data["users"][user_id]["attention_to_hulaquan"] = mode
        except KeyError:
            self.add_user(user_id)
            self.data["users"][user_id]["attention_to_hulaquan"] = mode
        return mode
    
    def new_subscribe(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id not in self.data["users_list"]:
            self.add_user(user_id)
        self.data["users"][user_id]["subscribe"]["is_subscribe"] = True
        self.data["users"][user_id]["subscribe"]["subscribe_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return True
   
    def add_ticket_subscribe(self, user_id, ticket_id):
       if not isinstance(user_id, str):
           user_id = str(user_id)
       if user_id not in self.data["users_list"]:
           self.add_user(user_id)
       self.data["users"][user_id]["subscribe"]["subscribe_tickets"].append(ticket_id)
       return True
   
