from ncatbot.utils import UniversalLoader, PERSISTENT_DIR
from datetime import datetime
import inspect
from pathlib import Path

class GroupsManager:
    def __init__(self, data: UniversalLoader = None):
        self.data = data
        if "groups" not in self.data:
            self.data["groups"] = {}
        if "groups_list" not in self.data:
            self.data["groups_list"] = []
        
    def groups(self):
        return self.data.get("groups", {})
        
    def groups_list(self):
        return self.data.get("groups_list", [])
        
    def add_group(self, group_id):
        if not isinstance(group_id, str):
            group_id = str(group_id)
        if group_id in self.data["groups_list"]:
            return
        self.data["groups_list"].append(group_id)
        self.data["groups"][group_id] = {
            "activate": True,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "attention_to_hulaquan": False,
        }
    
    def delete_group(self, group_id):
        if not isinstance(group_id, str):
            group_id = str(group_id)
        if group_id in self.data["groups_list"]:
            self.data["groups_list"].remove(group_id)
            del self.data["groups"][group_id]
            
    def switch_attention_to_hulaquan(self, group_id):
        if not isinstance(group_id, str):
            group_id = str(group_id)
        try:
            flag = self.data["groups"][group_id]["attention_to_hulaquan"]
        except KeyError:
            self.add_group(group_id)
            flag = self.data["groups"][group_id]["attention_to_hulaquan"]
        self.data["groups"][group_id]["attention_to_hulaquan"] = not flag
        return (not flag)
            