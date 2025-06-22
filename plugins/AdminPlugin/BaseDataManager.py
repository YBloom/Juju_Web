import json
import os
from ncatbot.utils import UniversalLoader

class BaseDataManager(UniversalLoader):
    def __init__(self, file_path, file_type = None):
        file_type = file_type or "json"
        super().__init__(file_path, file_type)
        
    def on_close(self):
        """卸载插件时的清理操作

        执行插件卸载前的清理工作,保存数据并注销事件处理器

        Raises:
            RuntimeError: 保存持久化数据失败时抛出
        """
        try:
            self.data.save()
        except Exception as e:
            raise RuntimeError(f"保存持久化数据时出错: {e}")

    def on_load(self):
        """加载插件时的初始化操作

        执行插件加载时的初始化工作,加载数据

        Raises:
            RuntimeError: 读取持久化数据失败时抛出
        """
        try:
            self.data.load()
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                open(self.file_path, "w").write("")
                self.data.save()
                self.data.load()
            else:
                raise RuntimeError(self.name, f"加载持久化数据时出错: {e}")
            
    async def aload(self):
        await super().aload()
        self._check_data()
        
    def load(self):
        super().load()
        self._check_data()
    
    def _check_data(self):
        pass
