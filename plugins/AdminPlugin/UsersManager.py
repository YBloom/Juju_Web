from ncatbot.utils import UniversalLoader, PERSISTENT_DIR
from datetime import datetime
import inspect
from pathlib import Path
from ncatbot.utils.logger import get_log
log = get_log()

class UsersManager:
    def __init__(self, data: UniversalLoader=None):
        self.is_get_managers = False #插件Hulaquan有没有捕获managers
        self.data = data
        if "users" not in self.data:
            self.data["users"] = {}
        if "users_list" not in self.data:
            self.data["users_list"] = []
        if "ops_list" not in self.data:
            self.data["ops_list"] = []
        
    def users(self):
        return self.data.get("users", {})
        
    def users_list(self):
        return self.data.get("users_list", [])
    
    def ops_list(self):
        return self.data.get("ops_list", [])
        
        
    def add_user(self, user_id):
        if not isinstance(user_id, str):
            user_id = str(user_id)
        if user_id in self.data["users_list"]:
            return
        self.data["users_list"].append(user_id)
        self.data["users"][user_id] = {
            "activate": True,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "attention_to_hulaquan": 0,
        }
    
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
   