from datetime import datetime, timedelta
from plugins.Hulaquan.utils import *
from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
from plugins.AdminPlugin.BaseDataManager import BaseDataManager
import aiohttp
import os, shutil
import copy
import json
import random
import asyncio
import re

"""
    更新思路：
    1.按照是否修改self将函数数据分类
    """



class HulaquanDataManager(BaseDataManager):
    """
    功能：
    1.存储/调取卡司排期数据
    2.根据卡司数据有效期刷新
    
    {
        "events":{}
        "update_time":datetime
    }
    """
    def __init__(self, file_path=None):
        #file_path = file_path or "data/Hulaquan/hulaquan_events_data.json"
        super().__init__(file_path)
        self.semaphore = asyncio.Semaphore(10)  # 限制并发量10
        
    def _check_data(self):
        self.data.setdefault("events", {})  # 确保有一个事件字典来存储数据
        self.data["pending_events_dict"] = self.data.get("pending_events_dict", {}) # 确保有一个pending_events_dict来存储待办事件
        self.data["ticket_id_to_casts"] = self.data.get("ticket_id_to_casts", {})

    async def get_events_dict_async(self):
        data = await self.search_all_events_async()
        data_dic = {"events": {}, "update_time": ""}
        keys_to_extract = ["id", "title", "location", "start_time", "end_time", "update_time", "deadline", "create_time"]
        for event in data:
            event_id = str(event["id"])
            if event_id not in data_dic["events"]:
                data_dic["events"][event_id] = {key: event.get(key, None) for key in keys_to_extract}
        data_dic["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return data_dic

    async def search_all_events_async(self):
        data = False
        cnt = 95
        while data is False:
            count, result = await self.search_events_data_by_recommendation_link_async(cnt, 0, True)
            data = result
            cnt -= 5
            if cnt != 90 and not data:
                print(f"获取呼啦圈数据失败，第{(19-cnt/5)}尝试。")
            if cnt == 0:
                raise Exception
        return data

    async def search_events_data_by_recommendation_link_async(self, limit=12, page=0, timeMark=True, tags=None):
        recommendation_url = "https://clubz.cloudsation.com/site/getevent.html?filter=recommendation&access_token="
        try:
            recommendation_url = recommendation_url + "&limit=" + str(limit) + "&page=" + str(page)
            async with aiohttp.ClientSession() as session:
                async with session.get(recommendation_url, timeout=8) as response:
                    json_data = await response.text()
                    json_data = json_data.encode().decode("utf-8-sig")  # 关键：去除BOM
                    json_data = json.loads(json_data)
                    if isinstance(json_data, bool):
                        return False, False
                    result = []
                    for event in json_data["events"]:
                        if not timeMark or (timeMark and event["timeMark"] > 0):
                            if not tags or (tags and any(tag in event["tags"] for tag in tags)):
                                result.append(event["basic_info"])
                    return json_data["count"], result
        except Exception as e:
            return f"Error fetching recommendation: {e}", False

        
    def _alias_file(self):
            return os.path.join("data", "data_manager", "alias.json")

    def load_alias(self):
        try:
            with open(self._alias_file(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_alias(self, alias_dict):
        with open(self._alias_file(), "w", encoding="utf-8") as f:
            json.dump(alias_dict, f, ensure_ascii=False, indent=2)

    def add_alias(self, event_id, alias):
        alias_dict = self.load_alias()
        event_id = str(event_id)
        if event_id not in alias_dict:
            alias_dict[event_id] = {"alias": {}}
        if alias not in alias_dict[event_id]["alias"]:
            alias_dict[event_id]["alias"][alias] = {"no_response_times": 0}
        self.save_alias(alias_dict)
        return True

    def del_alias(self, event_id, alias):
        alias_dict = self.load_alias()
        event_id = str(event_id)
        if event_id in alias_dict and alias in alias_dict[event_id]["alias"]:
            del alias_dict[event_id]["alias"][alias]
            self.save_alias(alias_dict)
            return True
        return False

    def set_alias_no_response(self, event_id, alias, reset=False):
        alias_dict = self.load_alias()
        event_id = str(event_id)
        if event_id in alias_dict and alias in alias_dict[event_id]["alias"]:
            if reset:
                alias_dict[event_id]["alias"][alias]["no_response_times"] = 0
            else:
                alias_dict[event_id]["alias"][alias]["no_response_times"] += 1
                if alias_dict[event_id]["alias"][alias]["no_response_times"] >= 2:
                    del alias_dict[event_id]["alias"][alias]
            self.save_alias(alias_dict)

    async def _update_events_data_async(self, data_dict=None, __dump=True):
        data_dict = data_dict or await self.get_events_dict_async()
        self.updating = True
        self.data["events"] = data_dict["events"]
        event_ids = list(self.data["events"].keys())
        # 并发批量更新
        await asyncio.gather(*(self._update_ticket_details_async(eid) for eid in event_ids))
        self.data["last_update_time"] = self.data.get("update_time", None)
        self.data["update_time"] = data_dict["update_time"]
        self.updating = False
        return self.data

    async def _update_ticket_details_async(self, event_id, data_dict=None):
        retry = 0
        while retry < 3:
            async with self.semaphore:
                try:
                    json_data = await self.search_event_by_id_async(event_id)
                    keys_to_extract = ["id","event_id","title", "start_time", "end_time","status","create_time","ticket_price","total_ticket", "left_ticket_count", "left_days", "valid_from"]
                    ticket_list = json_data["ticket_details"]
                    for i in range(len(ticket_list)):
                        ticket_list[i] = {key: ticket_list[i].get(key, None) for key in keys_to_extract}
                        if ticket_list[i]["total_ticket"] is None and ticket_list[i]["left_ticket_count"] is None:
                            del ticket_list[i]
                    if data_dict is None:
                        self.data["events"][event_id]["ticket_details"] = ticket_list
                        return self.data
                    else:
                        data_dict["events"][event_id]["ticket_details"] = ticket_list
                        return data_dict
                except asyncio.TimeoutError:
                    retry += 1
                    if retry >= 3:
                        print(f"event_id {event_id} 请求超时，已重试2次，跳过")
                        return
                    else:
                        print(f"event_id {event_id} 请求超时，重试第{retry}次……")
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"event_id {event_id} 请求异常：{e}")
                    return

    
    async def return_events_data(self):
        if not self.data.get("events", None):
            await self._update_events_data_async()
            print("呼啦圈数据已更新")
        return self.data["events"]

    async def search_eventID_by_name(self, event_name):
        data = await self.return_events_data()
        result = []
        for eid, event in data.items():
            title = event["title"]
            if re.search(event_name, title, re.IGNORECASE):
                result.append([eid, title])
        return result
    
    async def search_event_by_id_async(self, event_id):
        event_url = f"https://clubz.cloudsation.com/event/getEventDetails.html?id={event_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(event_url, timeout=15) as resp:
                json_data = await resp.text()
                json_data = json_data.encode().decode("utf-8-sig")  # 关键：去除BOM
                return json.loads(json_data)
        
    async def output_data_info(self):
        old_data = await self.return_events_data()
        for eid, event in old_data.items():
            print(eid, event["title"], event["end_time"], event["update_time"])
        
    # ------------------------------------------ #


    def get_max_ticket_content_length(self, tickets, ticket_title_key='title'):
        max_len = 0
        for ticket in tickets:
            s = f"{ticket[ticket_title_key]} 余票{ticket['left_ticket_count']}/{ticket['total_ticket']}"
            max_len = max(max_len, get_display_width(s))
        return max_len

    # -------------------Query------------------------------ #         
    # ---------------------Announcement--------------------- #
    async def compare_to_database_async(self, __dump=True):
        if __dump:
            old_data_all = copy.deepcopy(self.data)
            new_data_all = await self._update_events_data_async()
        else:
            old_data_all = self.data
            new_data_all = await self._update_events_data_async()
        try:
            return self.__compare_to_database(old_data_all, new_data_all)
        except Exception as e:
            self.save_data_cache(old_data_all, new_data_all, "error_announcement_cache")
            raise  # 重新抛出异常，便于外层捕获和处理

    def __compare_to_database(self, old_data_all, new_data_all):
        # 将新爬的数据与旧数据进行比较，找出需要更新的数据
        """
        __dump: bool, 是否将新数据写入文件
        Returns:
            update_data: list, 包含需要更新的事件数据
            None: 如果没有需要更新的数据
        """
        is_updated = False
        new_pending = False
        new_data = new_data_all.get("events", {})
        old_data = old_data_all.get("events", {})
        messages = []
        for eid, event in new_data.items(): # 一个id对应一部剧
            message = []
            if comp := self.compare_tickets(old_data.get(eid, {}), new_data[eid].get("ticket_details", None)):
                # 仅返回更新了的ticket detail
                new_message = []
                return_message = []
                add_message = []
                pending_message = {}
                for ticket in comp:
                    flag = ticket.get('update_status')
                    t = ("✨" if ticket['left_ticket_count'] > 0 else "❌") + f"{ticket['title']} 余票{ticket['left_ticket_count']}/{ticket['total_ticket']}"
                    if ticket["status"] == "pending" and 'update_status' in ticket.keys():
                        valid_from = ticket.get("valid_from")
                        if not valid_from or valid_from == "null":
                            valid_from = "未公开"
                        pending_message[valid_from] = []
                        pending_message[valid_from].append(t)
                    elif ticket["status"] == "active":
                        if flag == 'new':
                            if ticket["left_ticket_count"] == 0 and ticket['total_ticket'] == 0:
                                valid_from = ticket.get("valid_from")
                                if not valid_from or valid_from == "null":
                                    valid_from = "未公开（可能很快就开）"
                                pending_message[valid_from] = []
                                pending_message[valid_from].append(t)
                            else:
                                new_message.append(t)
                        elif flag == 'return':
                            return_message.append(t)
                        elif flag == 'add':
                            add_message.append(t)
                if pending_message:
                    new_pending = True
                    t = "🟡新上架场次：\n"
                    cnt = 1
                    for valid_from, m in pending_message.items():
                        s = (f"第{cnt}波" if len(pending_message.keys()) > 1 else None)+f"开票时间：{valid_from}\n"+'\n'.join(m)+"\n"
                        cnt += 1
                        random_id = random.randint(1000, 9999)
                        valid_date = standardize_datetime(valid_from, return_str=False)
                        while random_id in pending_message:
                            random_id = random.randint(1000, 9999)
                        self.data["pending_events_dict"][random_id] = {
                            "valid_from": valid_date,
                            "message": (f"剧名: {event['title']}\n"
                                        f"活动结束时间: {event['end_time']}\n"
                                        f"更新时间: {self.data['update_time']}\n"
                                        f"开票时间: {valid_from}\n"
                                        f"场次信息：\n" + '\n'.join(m) + "\n"
                                        )
                                        
                        }
                        t += s
                    message.append(t)
                if new_message:
                    message.append("🟢新开票场次：\n"+'\n'.join(new_message))
                if add_message:
                    message.append("🟢补票场次：\n"+'\n'.join(add_message))
                if return_message:
                    message.append("🟢回流（？）场次：\n"+'\n'.join(return_message))
            else:
                continue
            messages.append((
                f"剧名: {event['title']}\n"
                f"活动结束时间: {event['end_time']}\n"
                f"更新时间: {self.data['update_time']}\n"
            ) + "\n".join(message))
            is_updated = True
            if is_updated:
                self.save_data_cache(old_data_all, new_data_all, "update_data_cache")
        return {"is_updated": is_updated, "messages": messages, "new_pending": new_pending}

    def save_data_cache(self, old_data_all, new_data_all, cache_folder_name):
        cache_root = os.path.join(os.getcwd(), cache_folder_name)
        os.makedirs(cache_root, exist_ok=True)
                # 清理超过48小时的缓存
        now = datetime.now()
        for d in os.listdir(cache_root):
            dir_path = os.path.join(cache_root, d)
            if os.path.isdir(dir_path):
                try:
                            # 目录名格式为"2025-07-03_12-34-56"
                    dir_time = datetime.strptime(d, "%Y-%m-%d_%H-%M-%S")
                    if now - dir_time > timedelta(hours=48):
                        shutil.rmtree(dir_path)
                except Exception:
                    continue
                # 新建本次缓存
        update_time_str = str(self.data['update_time']).replace(":", "-").replace(" ", "_")
        cache_dir = os.path.join(cache_root, update_time_str)
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, "old_data_all.json"), "w", encoding="utf-8") as f:
            json.dump(old_data_all, f, ensure_ascii=False, indent=2)
        with open(os.path.join(cache_dir, "new_data_all.json"), "w", encoding="utf-8") as f:
            json.dump(new_data_all, f, ensure_ascii=False, indent=2)


    def compare_tickets(self, old_data_all, new_data):
        """
{
  "id": 31777,
  "event_id": 3863,
  "title": "《海雾》07-19 20:00￥199（原价￥299) 学生票",
  "start_time": "2025-07-19 20:00:00",
  "end_time": "2025-07-19 21:00:00",
  "status": "active", /expired, /pending
  "create_time": "2025-06-11 11:06:13",
  "ticket_price": 199,
  "max_ticket": 1,
  "total_ticket": 14,
  "left_ticket_count": 0,
  "left_days": 25,
}
        """
        if (not old_data_all) and new_data:
            for i in new_data:
                i["update_status"] = 'new'
                
            return new_data
        elif not (old_data_all and new_data):
            return None
        else:
            old_data = old_data_all.get("ticket_details", {})
        if not old_data:
            for i in new_data:
                i["update_status"] = 'new'
            return new_data
        old_data_dict = {item['id']: item for item in old_data}
        update_data = []
        # 遍历 new_data 并根据条件进行更新
        for new_item in new_data:
            new_id = new_item['id']
            new_left_ticket_count = new_item['left_ticket_count']
            new_total_ticket = new_item['total_ticket']     
            
            if new_id not in old_data_dict:
                # 如果 new_data 中存在新的 id，则标记为 "new"
                new_item['update_status'] = 'new'
                update_data.append(new_item)
            else:
                old_item = old_data_dict[new_id]
                old_left_ticket_count = old_item['left_ticket_count']
                old_total_ticket = old_item['total_ticket']
                if (new_total_ticket>0 and old_total_ticket==0):
                    new_item['update_status'] = 'new'
                    update_data.append(new_item)
                # 获取 old_data 中对应 id 的旧数据
                #print("new_item", new_item, "\nold item", old_item)
                elif old_total_ticket is None or (new_total_ticket > (old_total_ticket or 0)):
                    # 如果 total_ticket 增加了，则标记为 "add"
                    new_item['update_status'] = 'add'
                    update_data.append(new_item)
                elif old_left_ticket_count is None or (new_left_ticket_count > old_left_ticket_count and old_left_ticket_count == 0):
                    # 如果 left_ticket_count 增加了，则标记为 "return"
                    new_item['update_status'] = 'return'
                    update_data.append(new_item)
                else:
                    new_item['update_status'] = None
        return update_data
    
    
    async def get_ticket_cast_and_city_async(self, saoju: SaojuDataManager, eName, ticket, city=None):
        eid = ticket['id']
        event_id = ticket['event_id']
        has_no_city = ('city' not in ticket)
        has_no_cast = (eid not in self.data['ticket_id_to_casts'] or (self.data['ticket_id_to_casts'][eid]['cast'] == [])) 
        if has_no_city or has_no_cast:
            response = await saoju.search_for_musical_by_date_async(eName, ticket['start_time'], city=city)
            print(response)
            if not response:
                alias_dict = self.load_alias()
                print("alias_dict", alias_dict)
                aliases = alias_dict.get(str(event_id), {}).get("alias", {})
                for alias in list(aliases.keys()):
                    response = await saoju.search_for_musical_by_date_async(alias, ticket['start_time'], city=city)
                    if response:
                        self.set_alias_no_response(event_id, alias, reset=True)
                        break
                    else:
                        self.set_alias_no_response(event_id, alias, reset=False)
            if not response:
                return {"cast":[], "city":None}
            else:
                if has_no_cast:
                    cast = response.get("cast", [])
                    self.data['ticket_id_to_casts'][eid] = {}
                    self.data['ticket_id_to_casts'][eid]["event_id"] = ticket["event_id"]
                    self.data['ticket_id_to_casts'][eid]["cast"] = cast
                if has_no_city:
                    ticket['city'] = response.get('city', None)
        return {"cast": self.data['ticket_id_to_casts'][eid]['cast'], "city":ticket.get('city', None)}

    async def get_cast_artists_str_async(self, saoju, eName, ticket, city=None):
        cast = (await self.get_ticket_cast_and_city_async(saoju, eName, ticket, city))['cast']
        return " ".join([i["artist"] for i in cast])

    async def get_ticket_city_async(self, saoju, eName, ticket):
        return (await self.get_ticket_cast_and_city_async(saoju, eName, ticket))["city"]

    async def on_message_search_event_by_date(self, saoju, date, _city=None, ignore_sold_out=False):
        date_obj = standardize_datetime(date, with_second=False, return_str=False)
        result_by_city = {}
        city_events_count = {}
        for eid, event in self.data["events"].items():
            try:
                event_start = standardize_datetime(event["start_time"], with_second=False, return_str=False)
                event_end = standardize_datetime(event["end_time"], with_second=False, return_str=False)
            except Exception:
                continue
            if not (event_start.date() <= date_obj.date() <= event_end.date()):
                continue
            for ticket in event.get("ticket_details", []):
                if ignore_sold_out and ticket.get("left_ticket_count", 0)==0:
                    continue
                t_start = ticket.get("start_time")
                if not t_start:
                    continue
                try:
                    t_start = standardize_datetime(t_start, with_second=False, return_str=False)
                except Exception:
                    continue
                if t_start.date() != date_obj.date():
                    continue
                tInfo = extract_title_info(ticket.get("title", ""))
                event_title = tInfo['title'][1:-1]
                event_city = await self.get_ticket_city_async(saoju, event_title, ticket) or "未知城市"
                if _city:
                    if not event_city or _city not in event_city:
                        continue
                cast_str = await self.get_cast_artists_str_async(saoju, event_title, ticket, _city) or "无卡司信息"
                time_key = t_start.strftime("%H:%M")
                if event_city not in result_by_city:
                    result_by_city[event_city] = {}
                    result_by_city[event_city][time_key] = []
                    city_events_count[event_city] = 1
                elif time_key not in result_by_city[event_city]:
                    result_by_city[event_city][time_key] = []
                city_events_count[event_city] += 1
                result_by_city[event_city][time_key].append({
                    "event_title": tInfo['title'] + " " + tInfo["price"] + (f"(原价：{tInfo['full_price']})" if tInfo["full_price"] else ""),
                    "ticket_title": ticket.get("title", ""),
                    "cast": cast_str,
                    "left": ticket.get("left_ticket_count", "-"),
                    "total": ticket.get("total_ticket", "-"),
                })
        if not result_by_city:
            return f"{date} {_city or ''} 当天无呼啦圈学生票场次信息。"
        message = f"{date} {_city or ''} 呼啦圈学生票场次：\n"
        sorted_keys = sorted(city_events_count, key=lambda x: city_events_count[x], reverse=True)
        if "未知城市" in sorted_keys:
            sorted_keys.remove("未知城市")
            sorted_keys.append("未知城市")
        for city_key in sorted_keys:
            message += f"城市：{city_key}\n"
            for t in sorted(result_by_city[city_key].keys()):
                message += f"⏲️时间：{t}\n"
                for item in result_by_city[city_key][t]:
                    message += ("✨" if item['left'] > 0 else "❌") + f"{item['event_title']} 余票{item['left']}/{item['total']}" + " " + item["cast"] + "\n"
        message += f"\n数据更新时间: {self.data['update_time']}\n"
        return message

    async def generate_tickets_query_message(self, eid, eName, saoju:SaojuDataManager, show_cast=True, ignore_sold_out=False, refresh=False):  
        if not refresh:
            event_data = self.data["events"].get(str(eid), None)
        else:
            await self._update_ticket_details_async(eid)
            event_data = self.data["events"].get(str(eid), None)
        if event_data:
            title = event_data.get("title", "未知剧名")
            tickets_details = event_data.get("ticket_details", [])
            remaining_tickets = []
            for ticket in tickets_details:
                if ticket["status"] == "active":
                    if ticket["left_ticket_count"] > (0 if ignore_sold_out else -1):
                        remaining_tickets.append(ticket)
            max_ticket_info_count = self.get_max_ticket_content_length(remaining_tickets)
            url = f"https://clubz.cloudsation.com/event/{eid}.html"
            message = (
                f"剧名: {title}\n"
                f"购票链接：{url}\n"
                "剩余票务信息:\n"
                + ("\n".join([("✨" if ticket['left_ticket_count'] > 0 else "❌") 
                                + ljust_for_chinese(f"{ticket['title']} 余票{ticket['left_ticket_count']}/{ticket['total_ticket']}", max_ticket_info_count)
                                + ((" " + (await self.get_cast_artists_str_async(saoju, eName, ticket, 
                                                        city=extract_city(event_data.get("location", ""))
                                                    )
                                        )
                                ) if show_cast else "")
                                for ticket in remaining_tickets
                                ])
                if remaining_tickets else "暂无余票。")
                                )
            message += f"\n数据更新时间: {self.data['update_time']}\n"
            return message
        else:
            return "未找到该剧目的详细信息。"
        
    def get_ticket_cast_and_city(self, saoju: SaojuDataManager, eName, ticket, city=None):
        eid = ticket['id']
        has_no_city = ('city' not in ticket)
        has_no_cast = (eid not in self.data['ticket_id_to_casts'] or (self.data['ticket_id_to_casts'][eid]['cast'] == [])) 
        if has_no_city or has_no_cast:
            response = saoju.search_for_musical_by_date(eName,
                                                        ticket['start_time'], 
                                                        city=city)
            if not response:
                return {"cast":[], "city":None}
            else:
                if has_no_cast:
                    cast = response.get("cast", [])
                    self.data['ticket_id_to_casts'][eid] = {}
                    self.data['ticket_id_to_casts'][eid]["event_id"] = ticket["event_id"]
                    self.data['ticket_id_to_casts'][eid]["cast"] = cast
                if has_no_city:
                    ticket['city'] = response.get('city', None)
        return {"cast": self.data['ticket_id_to_casts'][eid]['cast'], "city":ticket.get('city', None)}
        
    def get_cast_artists_str(self, saoju, eName, ticket, city=None):
        cast = self.get_ticket_cast_and_city(saoju, eName, ticket, city)['cast']
        # return 演员卡司:: "丁辰西 陈玉婷 照余辉"
        return " ".join([i["artist"] for i in cast])
    
    def get_ticket_city(self, saoju, eName, ticket):
        return self.get_ticket_cast_and_city(saoju, eName, ticket)['city']
    
            
    async def on_message_tickets_query(self, eName, saoju, ignore_sold_out=False, show_cast=True, refresh=False):
        result = await self.search_eventID_by_name(eName)
        if len(result) > 1:
            queue = [f"{i}. {event[1]}" for i, event in enumerate(result, start=1)]
            return f"找到多个匹配的剧名，请重新以唯一的关键词查询：\n" + "\n".join(queue)
        elif len(result) == 1:
            eid = result[0][0]
            return await self.generate_tickets_query_message(eid, eName, saoju, show_cast=show_cast, ignore_sold_out=ignore_sold_out, refresh=refresh)
        else:
            return "未找到该剧目。"
        
    async def message_update_data_async(self):
        query_time = datetime.now()
        query_time_str = query_time.strftime("%Y-%m-%d %H:%M:%S")
        result = await self.compare_to_database_async()
        is_updated = result["is_updated"]
        messages = result["messages"]
        new_pending = result["new_pending"]
        if not is_updated:
            return {"is_updated": False, "messages": [f"无更新数据。\n查询时间：{query_time_str}\n上次数据更新时间：{self.data['last_update_time']}",], "new_pending": False}
        messages = [f"检测到呼啦圈有{len(messages)}条数据更新\n查询时间：{query_time_str}"] + messages
        return {"is_updated": is_updated, "messages": messages, "new_pending": new_pending}
