from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
from plugins.Hulaquan.StatsDataManager import StatsDataManager
from plugins.Hulaquan.AliasManager import AliasManager
from plugins.Hulaquan.HulaquanDataManager import HulaquanDataManager
from plugins.AdminPlugin.UsersManager import UsersManager
from plugins.Hulaquan import BaseDataManager
from ncatbot.utils.logger import get_log



log = get_log()
User = UsersManager()
Alias = AliasManager()
Stats = StatsDataManager()
Saoju = SaojuDataManager()
Hlq = HulaquanDataManager()

managers: list[BaseDataManager] = [User, Stats, Saoju, Hlq, Alias]
async def save_all(on_close=False):
    success = 1
    for manager in managers:
        result = await manager.save(on_close)
        success *= int(result['success'])
    return bool(success)