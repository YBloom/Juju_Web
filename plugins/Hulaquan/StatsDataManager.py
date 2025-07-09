from datetime import datetime, timedelta
from plugins.AdminPlugin.BaseDataManager import BaseDataManager
from plugins.Hulaquan.utils import *


class StatsDataManager(BaseDataManager):
    """
    功能：
    进行数据统计
    """
    def __init__(self, file_path=None):
        super().__init__(file_path)

    def _check_data(self):
        self.data.setdefault("on_command_times", {})
        
    def on_command(self, command_name):
        self.data["on_command_times"].setdefault(command_name, 0)
        self.data["on_command_times"][command_name] += 1
        
    def get_on_command_times(self, command_name):
        return self.data["on_command_times"][command_name]