import json
import os

class BaseDataManager:
    def __init__(self, file_path):
        self.work_path = "data/data_manager/"
        self.file_path = file_path or f"{self.work_path}{self.__class__.__name__}.json"
        self.data = {}
        self.updating = False
        self.on_load()
        
    def on_close(self):
        """卸载插件时的清理操作

        执行插件卸载前的清理工作,保存数据并注销事件处理器

        Raises:
            RuntimeError: 保存持久化数据失败时抛出
        """
        self.save()

    def on_load(self):
        """加载插件时的初始化操作

        执行插件加载时的初始化工作,加载数据

        Raises:
            RuntimeError: 读取持久化数据失败时抛出
        """
        try:
            if os.path.exists(self.file_path):
                self.load()
            elif not os.path.exists(self.work_path):
                os.makedirs(self.work_path)
                open(self.file_path, "w", encoding="utf-8").write(json.dumps({}))
            else:
                open(self.file_path, "w", encoding="utf-8").write(json.dumps({}))
        except Exception as e:
                raise RuntimeError(self.__class__.__name__, f"加载持久化数据时出错: {e.title()} - {e}")
        
    def load(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            try:
                self.data = json.load(f)
            except json.JSONDecodeError as e:
                self.data = {}
        self._check_data()
        
    def save(self):
        try:
            if self.updating:
                raise RuntimeError(f"保存持久化数据时出错: {e}")
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            raise RuntimeError(f"保存持久化数据时出错: {e}")
        
    def _check_data(self):
        pass
