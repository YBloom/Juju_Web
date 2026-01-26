import logging
from typing import List, Union, Optional
from datetime import datetime

from services.bot.commands.base import CommandHandler, CommandContext
from services.bot.commands.registry import register_command
from services.hulaquan.formatter import HulaquanFormatter

log = logging.getLogger(__name__)

# --- Helper ---
def parse_price_filters(args: List[str]) -> List[float]:
    filters = []
    for arg in args:
        if arg == "-all": continue
        try:
            # remove leading dash e.g. -219 -> 219
            # but preserve negative numbers if that were a thing, though prices are positive.
            # actually our convention is -219 means filter for price 219.
            p = float(arg.lstrip("-"))
            filters.append(p)
        except ValueError:
            continue
    return filters

@register_command
class HlqSearchCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/hlq", "/hulaquan", "/呼啦圈", "/search", "查剧", "搜剧", "搜演出", "查票", "/query"]

    @property
    def help_text(self) -> str:
        return (
            "🔍 1. 剧目余票查询\n"
            "用法: /hlq [剧名] [参数...]\n"
            "搜索呼啦圈平台上的学生票/折扣票信息，支持按城市、价格筛选。\n\n"
            "示例:\n"
            "• 基础查询：/hlq 连璧\n"
            "• 指定城市：/hlq 时光代理人 上海\n"
            "• 指定价格：/hlq 连璧 -199 (仅看199元票档)\n"
            "• 忽略售罄：/hlq 连璧 -i (仅看有票场次)\n"
            "• 查看全部：/hlq 连璧 -all (查看全部排期)\n"
            "• 组合使用：/hlq 连璧 上海 -219 -all"
        )

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        query = " ".join(ctx.text_args)
        if not query:
            return self.help_text
        
        show_all = "-all" in ctx.mode_args
        ignore_sold_out = "-i" in ctx.mode_args
        price_filters = parse_price_filters(ctx.mode_args)

        # 1. 采用统一的智能搜索
        results = await ctx.service.search_events_smart(query)
        
        if not results:
            return f"❌ 未找到包含 '{query}' 的剧目。"
        
        # 2. 如果结果仍多于1个，且没有足够精确，提示用户（保持交互一致性）
        if len(results) > 1:
            # 为了一致性，我们也返回选择列表
            msg = [f"🔍 找到 {len(results)} 个相关剧目，请通过城市进一步筛选：\n"]
            for i, event in enumerate(results, 1):
                city_str = f"【{event.city}】" if event.city else ""
                if event.city and (f"【{event.city}】" in event.title or f"[{event.city}]" in event.title):
                    display = event.title
                else:
                    display = f"{city_str}{event.title}"
                msg.append(f"{i}. {display}")
            
            # 提供示例引导
            first_city = results[0].city or "上海"
            msg.append(f"\n💡 示例：`/hlq {query} {first_city}`")
            return "\n".join(msg)
        
        # 3. 只有一个结果，返回详情
        event = results[0]
        
        # 应用忽略售罄筛选
        if ignore_sold_out:
            # 注意：这里会修改 event 对象的 tickets 列表引用，但这只是内存中的副本，不应该影响数据库
            # 但如果是同一个 session 查询出来的对象，修改它是否安全？
            # 这是一个潜在风险点。如果其他协程也引用了这个 event 对象。
            # 为了安全起见，我们最好不要修改 event.tickets，而是传递过滤后的列表给 formatter
            pass 

        # 既然 format_event_search_result 内部会读取 event.tickets
        # 我们这里只能临时修改它，或者让 formatter 支持传入 tickets
        # 查看 HulaquanFormatter.format_event_search_result 源码...
        # 它直接读取 event.tickets。
        # 既然我们是在重构，为了避免这种副作用，最好是做一层浅拷贝或者在 formatter 里处理。
        # 但现在只是搬运代码，先保持原有逻辑，但要注意这个隐患。
        # 原有逻辑：event.tickets = [t for t in event.tickets if t.stock > 0]
        # 只要这不仅 session add/commit，就不会影响数据库。
        
        original_tickets = event.tickets
        filtered_tickets = list(original_tickets)

        if ignore_sold_out:
            filtered_tickets = [t for t in filtered_tickets if t.stock > 0]
            if not filtered_tickets:
                return f"🔍 《{event.title}》 所有学生票场次均已售罄 (使用 -all 查看或去除 -i)"

        # 应用价格筛选
        if price_filters:
            filtered_tickets = [t for t in filtered_tickets if t.price in price_filters]
            if not filtered_tickets:
                price_strs = ", ".join([f"￥{int(p)}" for p in price_filters])
                return f"🔍 在 《{event.title}》 中未找到价格为 {price_strs} 的学生票。"

        # 临时替换 tickets 用于格式化
        # TODO: Refactor formatter to accept tickets argument
        event.tickets = filtered_tickets
        try:
            return HulaquanFormatter.format_event_search_result(event, show_all=show_all)
        finally:
            # 还原，虽然不一定必要，但好习惯
            event.tickets = original_tickets


@register_command
class DateQueryCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/date", "/日期", "/calendar", "查排期", "日历", "排期"]

    @property
    def help_text(self) -> str:
        return (
            "📅 2. 日期排期查询\n"
            "用法: /date [日期] [城市] [-all]\n"
            "按日期查看全站（或指定城市）的学生票演出排期。\n\n"
            "示例:\n"
            "• 查今天：/date\n"
            "• 查指定日期：/date 2026-02-14\n"
            "• 查指定城市：/date 2026-01-20 上海"
        )

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        text_args = ctx.text_args
        show_all = "-all" in ctx.mode_args
        
        date_str = text_args[0] if text_args else datetime.now().strftime("%Y-%m-%d")
        
        # 尝试解析日期，如果第一个参数不是日期，可能是单纯的城市（默认为今天）
        # 但原来的逻辑是：text_args[0] 是 date_str。
        # 如果用户只输入 /date 上海，则 text_args[0] = "上海"。
        # "上海" 按照 %Y-%m-%d 解析会报错。
        
        target_date = None
        city = None
        
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            # 如果成功，第二个参数可能是城市
            if len(text_args) > 1:
                city = text_args[1]
        except ValueError:
            # 如果第一个参数解析失败，可能它是城市，且想查今天
            # 或者它就是无效的日期格式
            # 原来的逻辑比较简单 crude：直接报错返回帮助。
            # 这里我们可以稍微智能一点？不，保持原样最安全。
            # 原本逻辑：
            # try: target_date = datetime.strptime(date_str, "%Y-%m-%d")
            # except ValueError: return self.CMD_HELP_DATE
            
            # 但用户如果输入 /date 上海，确实会报错。
            # 为了更好的体验，如果解析失败，我们检测它是否像日期。
            # 如果不像，就认为是城市，日期设为今天。
            if "-" not in date_str and not date_str.isdigit():
                 target_date = datetime.now()
                 city = date_str
            else:
                 return self.help_text

        results = await ctx.service.get_events_by_date(target_date, city)
        
        if not results:
            date_display = target_date.strftime("%Y-%m-%d")
            msg = f"📅 {date_display}"
            if city:
                msg += f" ({city})"
            msg += " 暂无收录的学生票演出信息。"
            return msg
        
        return HulaquanFormatter.format_date_events(target_date, results, show_all=show_all)

@register_command
class CastQueryCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/cast", "/同场", "/同场演员", "查同场", "同台"]

    @property
    def help_text(self) -> str:
        return (
            "👥 3. 同场卡司查询\n"
            "用法: /cast [演员1] [演员2] ... [参数]\n"
            "搜索一位或多位演员的未来同场演出排期。\n\n"
            "示例:\n"
            "• 双人同场：/cast 丁辰西 陈玉婷\n"
            "• 显示同场其它卡司：/cast 陈玉婷 -o\n"
            "• 仅查此演员在呼啦圈中的场次：/cast 丁辰西 -h"
        )
    
    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        actors = ctx.text_args
        if not actors:
            return self.help_text
        
        show_others = "-o" in ctx.mode_args
        use_hulaquan = "-h" in ctx.mode_args
        
        start_date = datetime.now().strftime("%Y-%m-%d")
        actors_str = " ".join(actors)
        
        # 仍然需要 import 配置文件中的 web base url? 
        # 或者我们直接硬编码或者从 ctx 获取？
        # 暂时硬编码或从环境变量取，或者放在 Config 模块里。
        # BotHandler 里是硬编码定义的。
        WEB_BASE_URL = "https://yyj.yaobii.com" # TODO: Move to unified config
        
        if use_hulaquan:
            # 使用呼啦圈本地数据
            try:
                results = await ctx.service.search_co_casts(actors)
                if not results:
                    return f"❌ 在呼啦圈系统中未找到 {actors_str} 的同场演出学生票"
                
                web_link = f"{WEB_BASE_URL}/?tab=cocast&actors={','.join(actors)}"
                return HulaquanFormatter.format_co_casts(results, limit=30, show_link=web_link)
            except Exception as e:
                log.error(f"Hulaquan co-cast search failed: {e}")
                return "查询失败，请稍后重试。"
        else:
            # 使用扫剧系统
            try:
                results = await ctx.service.saoju.match_co_casts(
                    actors, show_others=show_others, start_date=start_date
                )
                
                if not results:
                    return f"👥 未找到 {actors_str} 在 {start_date} 之后的同台演出。"
                
                web_link = f"{WEB_BASE_URL}/?tab=cocast&actors={','.join(actors)}"
                return HulaquanFormatter.format_co_casts(results, limit=30, show_link=web_link)
            except Exception as e:
                log.error(f"Saoju co-cast search failed: {e}")
                return "查询失败，扫剧系统可能暂时不可用。"
