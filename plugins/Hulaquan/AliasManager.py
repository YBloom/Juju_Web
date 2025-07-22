from plugins.Hulaquan import BaseDataManager


class AliasManager(BaseDataManager):
    """
    功能：
    别名系统
    """
    def __init__(self, file_path="data/data_manager/alias.json", *args, **kwargs):
        super().__init__(file_path, *args, **kwargs)
        # 新数据结构
        

    def on_load(self, *args, **kwargs):
        # 别名系统数据结构说明：
        # alias_to_event: {alias -> event_id}  # alias为用户设置的别名，不能直接用于外部系统检索
        # event_to_names: {event_id -> [search_name, ...]}  # search_name为可在外部系统检索到event的正式名称或关键词
        # name_to_event: {search_name -> event_id}  # search_name可直接检索event
        # no_response: {alias:search_name -> int}  # 记录alias+search_name组合的无响应次数
        # 旧数据自动迁移
        if self.data and not self.data.get("alias_to_event") and any(isinstance(v, dict) and "search_names" in v for v in self.data.values()):
            self.migrate_old_data(self.data)
        if not self.data or not self.data.get("alias_to_event"):
            self.data = {
                "alias_to_event": {},
                "event_to_names": {},
                "name_to_event": {},
                "no_response": {}
            }

    def add_alias(self, event_id, alias):
        """
        添加别名（alias），alias为用户设置的别名，不能直接用于外部系统检索。
        """
        event_id = str(event_id)
        alias = alias.strip().lower()
        self.data["alias_to_event"][alias] = event_id
        # 不自动添加到 event_to_names
        return True

    def add_search_name(self, event_id, search_name):
        """
        添加可检索名（search_name），search_name为可在外部系统检索到event的正式名称或关键词。
        """
        event_id = str(event_id)
        search_name = search_name.strip()
        self.data["event_to_names"].setdefault(event_id, [])
        if search_name not in self.data["event_to_names"][event_id]:
            self.data["event_to_names"][event_id].append(search_name)
        self.data["name_to_event"][search_name] = event_id
        return True

    def delete_alias(self, alias):
        alias = alias.strip().lower()
        event_id = self.data["alias_to_event"].pop(alias, None)
        if event_id:
            # 不影响 event_to_names
            # 删除 no_response
            for k in list(self.data["no_response"].keys()):
                if k.startswith(f"{alias}:"):
                    del self.data["no_response"][k]
            return True
        return False

    def delete_search_name(self, event_id, search_name):
        event_id = str(event_id)
        search_name = search_name.strip()
        if event_id in self.data["event_to_names"]:
            self.data["event_to_names"][event_id] = [n for n in self.data["event_to_names"][event_id] if n != search_name]
            if not self.data["event_to_names"][event_id]:
                del self.data["event_to_names"][event_id]
        self.data["name_to_event"].pop(search_name, None)
        return True

    def set_no_response(self, alias, search_name, reset=False):
        key = f"{alias}:{search_name}"
        if reset:
            self.data["no_response"][key] = 0
        else:
            self.data["no_response"][key] = self.data["no_response"].get(key, 0) + 1
            if self.data["no_response"][key] >= 2:
                self.delete_alias(alias)

    def get_search_names(self, event_id):
        event_id = str(event_id)
        return self.data["event_to_names"].get(event_id, [])

    def get_event_id_by_alias(self, alias):
        alias = alias.strip().lower()
        return self.data["alias_to_event"].get(alias)

    def get_event_id_by_name(self, search_name):
        return self.data["name_to_event"].get(search_name.strip())

    def migrate_old_data(self, old_data):
        """
        迁移旧别名数据结构到新结构
        旧结构：{alias: {alias, search_names, event_id, ...}}
        新结构：见上
        """
        new_data = {
            "alias_to_event": {},
            "event_to_names": {},
            "name_to_event": {},
            "no_response": {}
        }
        for alias, info in old_data.items():
            if not isinstance(info, dict) or "event_id" not in info:
                continue
            event_id = str(info["event_id"])
            new_data["alias_to_event"][alias] = event_id
            new_data["event_to_names"].setdefault(event_id, [])
            for search_name in info.get("search_names", {}):
                if search_name not in new_data["event_to_names"][event_id]:
                    new_data["event_to_names"][event_id].append(search_name)
                new_data["name_to_event"][search_name] = event_id
                # 迁移无响应次数
                no_resp = info["search_names"][search_name].get("no_response_times", 0)
                if no_resp:
                    new_data["no_response"][f"{alias}:{search_name}"] = no_resp
        self.data = new_data

    def delete(self, alias):
        alias = alias.strip().lower()
        event_id = self.data["alias_to_event"].pop(alias, None)
        if event_id:
            # 删除 event_to_names
            if event_id in self.data["event_to_names"]:
                self.data["event_to_names"][event_id] = [n for n in self.data["event_to_names"][event_id] if n != alias]
                if not self.data["event_to_names"][event_id]:
                    del self.data["event_to_names"][event_id]
            # 删除 name_to_alias
            for n in list(self.data["name_to_alias"].keys()):
                if self.data["name_to_alias"][n] == alias:
                    del self.data["name_to_alias"][n]
            # 删除 no_response
            for k in list(self.data["no_response"].keys()):
                if k.startswith(f"{alias}:"):
                    del self.data["no_response"][k]
            return True
        return False

    def set_no_response(self, alias, search_name, reset=False):
        key = f"{alias}:{search_name}"
        if reset:
            self.data["no_response"][key] = 0
        else:
            self.data["no_response"][key] = self.data["no_response"].get(key, 0) + 1
            if self.data["no_response"][key] >= 2:
                self.delete(alias)

    def search_names(self, alias):
        alias = alias.strip().lower()
        event_id = self.data["alias_to_event"].get(alias)
        if event_id:
            return self.data["event_to_names"].get(event_id, [])
        return []

    def get_event_id(self, name):
        alias = self.data["name_to_alias"].get(name.strip())
        if alias:
            return self.data["alias_to_event"].get(alias)
        return None

    def migrate_old_data(self, old_data):
        """
        迁移旧别名数据结构到新结构
        旧结构：{alias: {alias, search_names, event_id, ...}}
        新结构：见上
        """
        new_data = {
            "alias_to_event": {},
            "event_to_names": {},
            "name_to_alias": {},
            "no_response": {}
        }
        for alias, info in old_data.items():
            if not isinstance(info, dict) or "event_id" not in info:
                continue
            event_id = str(info["event_id"])
            new_data["alias_to_event"][alias] = event_id
            new_data["event_to_names"].setdefault(event_id, [])
            if alias not in new_data["event_to_names"][event_id]:
                new_data["event_to_names"][event_id].append(alias)
            for search_name in info.get("search_names", {}):
                if search_name not in new_data["event_to_names"][event_id]:
                    new_data["event_to_names"][event_id].append(search_name)
                new_data["name_to_alias"][search_name] = alias
                # 迁移无响应次数
                no_resp = info["search_names"][search_name].get("no_response_times", 0)
                if no_resp:
                    new_data["no_response"][f"{alias}:{search_name}"] = no_resp
            new_data["name_to_alias"][alias] = alias
        self.data = new_data