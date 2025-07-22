from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
from plugins.Hulaquan.StatsDataManager import StatsDataManager
from plugins.Hulaquan.AliasManager import AliasManager
from plugins.Hulaquan.HulaquanDataManager import HulaquanDataManager
from plugins.AdminPlugin.UsersManager import UsersManager
from ncatbot.utils.logger import get_log



log = get_log()
Saoju = SaojuDataManager()
Hlq = HulaquanDataManager()
Stats = StatsDataManager()
User = UsersManager()
Alias = AliasManager()

async def save():
    await User.save()
    await Stats.save()
    await Saoju.save()
    await Hlq.save()
    await Alias.save()