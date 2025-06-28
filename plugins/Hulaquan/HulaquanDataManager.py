from datetime import datetime
import unicodedata
from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
import requests
import re
import aiohttp
import asyncio
import json
from plugins.AdminPlugin.BaseDataManager import BaseDataManager

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
        
    def _check_data(self):
        self.data.setdefault("events", {})  # 确保有一个事件字典来存储数据

    def fetch_and_update_data(self):
        """更新数据

        Returns:
            返回(old_data, new_data)
        """
        old_data = self.data
        self._update_events_data()
        return old_data, self.data

    def search_events_data_by_recommendation_link(self, limit=12, page=0, timeMark=True, tags=None):
        # get events from recommendation API
        recommendation_url = "https://clubz.cloudsation.com/site/getevent.html?filter=recommendation&access_token="
        try:
            recommendation_url = recommendation_url + "&limit=" + str(limit) + "&page=" + str(page)
            response = requests.get(recommendation_url)
            response.raise_for_status()
            json_data = response.content.decode('utf-8-sig')
            json_data = json.loads(json_data)
            result = []
            for event in json_data["events"]:
                if not timeMark or (timeMark and event["timeMark"] > 0):
                    if not tags or (tags and any(tag in event["tags"] for tag in tags)):
                        result.append(event["basic_info"])
        except requests.RequestException as e:
            return f"Error fetching recommendation: {e}"
        return json_data["count"], result

    def _update_events_data(self, data_dict=None):
        try:
            #self.update(json.dumps(data_dict or self.get_events_dict(), ensure_ascii=False))
            data_dict = data_dict or self.get_events_dict()
            self.data["events"] = data_dict["events"]
            for eid in list(self.data["events"].keys()):
                self._update_ticket_details(eid)
            self.data["last_update_time"] = self.data["update_time"]
            self.data["update_time"] = data_dict["update_time"]
            return self.data
        except Exception as e:
            print(f"呼啦圈数据下载失败: {e}")
            return None
    
    async def fetch_event_detail(self, session, event_id):
        url = f"https://clubz.cloudsation.com/event/getEventDetails.html?id={event_id}"
        async with session.get(url, timeout=8) as resp:
            try:
                return await resp.json()
            except requests.RequestException as e:
                print(f"Error fetching event details: {e}")
                return None
    
    async def fetch_ticket_details_batch_async(self, event_ids):
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_event_detail(session, eid) for eid in event_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return {eid: res for eid, res in zip(event_ids, results)} 
           
    async def fetch_and_update_data_async(self):
        """
        异步更新数据，功能对标 fetch_and_update_data（同步版）

        Returns:
            返回(old_data, new_data)
        """
        old_data = self.data.copy()
        # 1. 获取所有事件（只含基本信息和update_time）
        events = await self.fetch_events_list_async()
        # 2. 对比本地events，找出update_time有变化的event_id
        changed_event_ids = []
        for eid, event in events.items():
            if eid not in self.data["events"] or event["update_time"] != self.data["events"][eid]["update_time"]:
                changed_event_ids.append(eid)
        # 3. 并发请求变动事件的票务详情
        details = await self.fetch_ticket_details_batch_async(changed_event_ids)
        # 4. 更新本地数据
        for eid in changed_event_ids:
            if eid in self.data["events"]:
                self.data["events"][eid].update(details[eid])
            else:
                self.data["events"][eid] = details[eid]
        self.data["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return old_data, self.data

    async def fetch_events_list_async(self):
        """
        异步获取所有事件（只含基本信息和update_time），返回格式与 get_events_dict()["events"] 一致
        """
        url = "https://clubz.cloudsation.com/site/getevent.html?filter=recommendation&access_token=&limit=100&page=0"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=8) as resp:
                json_data = await resp.text()
                json_data = json.loads(json_data)
                events = {}
                keys_to_extract = ["id", "title", "location", "start_time", "end_time", "update_time", "deadline", "create_time"]
                for event in json_data["events"]:
                    event_id = str(event["id"])
                    events[event_id] = {key: event.get(key, None) for key in keys_to_extract}
                return events

    def search_ticket_details(self, event_id):
        json_data = self.search_event_by_id(event_id)
        keys_to_extract = ["id","event_id","title", "start_time", "end_time","status","create_time","ticket_price","total_ticket", "left_ticket_count", "left_days"]
        json_data: list = json_data["ticket_details"]
        for i in range(len(json_data)):
            json_data[i] = {key: json_data[i].get(key, None) for key in keys_to_extract}
            if json_data[i]["total_ticket"] is None and json_data[i]["left_ticket_count"] is None:
                del json_data[i]
        return json_data
        
    def _update_ticket_details(self, event_id):
        self.data["events"][event_id]["ticket_details"] = self.search_ticket_details(event_id)
        
    def get_events_dict(self):
        data = self.search_all_events()
        data_dic = {"events":{}, "update_time":""}
        keys_to_extract = ["id", "title", "location", "start_time", "end_time", "update_time", "deadline", "create_time"]
        for event in data:
            event_id = str(event["id"])
            if event_id not in data_dic["events"]:
                data_dic["events"][event_id] = {key: event.get(key, None) for key in keys_to_extract}
        data_dic["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return data_dic

    def search_all_events(self):
        #count = self.get_recommendation(1,0,False)[0]  # Test the connection and the count
        #print(f"Total recommendations available: {count}")
        data = []
        data += self.search_events_data_by_recommendation_link(100, 0, True)[1]
        return data
    
    def return_events_data(self):
        if not self.data.get("events", None):
            self._update_events_data()
            print("呼啦圈数据已更新")
        return self.data["events"]

    def search_eventID_by_name(self, event_name):
        data = self.return_events_data()
        result = []
        for eid, event in data.items():
            title = event["title"]
            if re.search(event_name, title, re.IGNORECASE):
                result.append([eid, title])
        return result
        
    def search_event_by_id(self, event_id):
        # 根据eid查找事件详细信息 主要用来获取余票信息
        event_url = f"https://clubz.cloudsation.com/event/getEventDetails.html?id={event_id}"
        try:
            response = requests.get(event_url)
            response.raise_for_status()
            json_data = response.content.decode('utf-8-sig')
            json_data = json.loads(json_data)
            return json_data
        except requests.RequestException as e:
            print(f"Error fetching event details: {e}")
            return None


        
    def output_data_info(self):
        old_data = self.return_events_data()
        for eid, event in old_data.items():
            print(eid, event["title"], event["end_time"], event["update_time"])
        
    # ------------------------------------------ #


    def get_max_ticket_content_length(self, tickets):
        max_len = 0
        for ticket in tickets:
            s = f"{ticket['title']} 余票{ticket['left_ticket_count']}/{ticket['total_ticket']}"
            max_len = max(max_len, get_display_width(s))
        return max_len

    # -------------------Query------------------------------ #         
    # ---------------------Announcement--------------------- #

    def compare_to_database(self):
        # 将新爬的数据与旧数据进行比较，找出需要更新的数据
        """
        __dump: bool, 是否将新数据写入文件
        Returns:
            update_data: list, 包含需要更新的事件数据
            None: 如果没有需要更新的数据
        """
        
        is_updated = False
        old_data_all, new_data_all = self.fetch_and_update_data()
        new_data = new_data_all["events"]
        old_data = old_data_all["events"]
        messages = []
        for eid, event in new_data.items():
            message = []
            old_event = old_data[eid]
            if eid not in old_data.keys():
                t = [f"✨" if ticket['left_ticket_count'] > 0 else "❌" + f"{ticket['title']} 余票{ticket['left_ticket_count']}/{ticket['total_ticket']}" for ticket in event.get("ticket_details", [])]
                message.append("🟢新开票场次：" + "\n ".join(t))
            elif comp := self.compare_tickets(old_event.get("ticket_details", None), new_data[eid].get("ticket_details", None)):
                new_message = []
                return_message = []
                add_message = []
                for ticket in comp:
                    flag = ticket['update_status']
                    t = f"✨" if ticket['left_ticket_count'] > 0 else "❌" + f"{ticket['title']} 余票{ticket['left_ticket_count']}/{ticket['total_ticket']}"
                    if flag == 'new':
                        new_message.append(t)
                    elif flag == 'return':
                        return_message.append(t)
                    elif flag == 'add':
                        add_message.append(t)
                if new_message:
                    message.append("🟢新开票场次："+'\n'.join(new_message))
                if return_message:
                    message.append("🟢回流（？）场次："+'\n'.join(return_message))
                if add_message:
                    message.append("🟢补票场次："+'\n'.join(add_message))
            else:
                continue
            messages.append((
                f"剧名: {event['title']}\n"
                f"活动结束时间: {event['end_time']}\n"
                f"更新时间: {event['update_time']}\n"
            ) + "\n".join(message))
            is_updated = True
        return is_updated, messages

    def compare_tickets(self, old_data, new_data):
        """
{
  "id": 31777,
  "event_id": 3863,
  "title": "《海雾》07-19 20:00￥199（原价￥299) 学生票",
  "start_time": "2025-07-19 20:00:00",
  "end_time": "2025-07-19 21:00:00",
  "status": "active", /expired
  "create_time": "2025-06-11 11:06:13",
  "ticket_price": 199,
  "max_ticket": 1,
  "total_ticket": 14,
  "left_ticket_count": 0,
  "left_days": 25,
}
        """
        if not (old_data and new_data):
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
                # 获取 old_data 中对应 id 的旧数据
                old_item = old_data_dict[new_id]
                old_left_ticket_count = old_item['left_ticket_count']
                old_total_ticket = old_item['total_ticket']
                #print("new_item", new_item, "\nold item", old_item)
                if new_total_ticket > old_total_ticket:
                    # 如果 total_ticket 增加了，则标记为 "add"
                    new_item['update_status'] = 'add'
                    update_data.append(new_item)
                elif new_left_ticket_count > old_left_ticket_count:
                    # 如果 left_ticket_count 增加了，则标记为 "return"
                    new_item['update_status'] = 'return'
                    update_data.append(new_item)
                else:
                    new_item['update_status'] = None
        return update_data
        
        
    def on_message_tickets_query(self, eName, saoju, ignore_sold_out=False, show_cast=True):
        query_time = datetime.now()
        result = self.search_eventID_by_name(eName)
        if len(result) > 1:
            queue = [f"{i}. {event[1]}" for i, event in enumerate(result, start=1)]
            return f"找到多个匹配的剧名，请重新以唯一的关键词查询：\n" + "\n".join(queue)
        elif len(result) == 1:
            eid = result[0][0]
            return self.generate_tickets_query_message(eid, query_time, eName, saoju, show_cast=show_cast, ignore_sold_out=ignore_sold_out)
        else:
            return "未找到该剧目。"

    def generate_tickets_query_message(self, eid, query_time, eName, saoju:SaojuDataManager, show_cast=True, ignore_sold_out=False):
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
                                + ((" " + (" ".join(saoju.search_casts_by_date_and_name(eName, 
                                                                                ticket['start_time'], 
                                                                                city=extract_city(event_data.get("location", ""))
                                                                                )
                                                )
                                        )
                                ) if show_cast else "")
                                for ticket in remaining_tickets
                                ])
                if remaining_tickets else "暂无余票。")
                                )
            message += f"数据更新时间: {self.data['update_time']}\n"
            return message
        else:
            return "未找到该剧目的详细信息。"
        
    def message_update_data(self):
        """
        Checks for updates in the data and returns update status and messages.

        Returns:
            tuple:
                - is_updated (bool): True if there is updated data, False otherwise.
                - messages (list of str): List of messages describing the update status and details.
        """
        # Return: (is_updated: bool, messages: [list:Str])
        query_time = datetime.now()
        query_time_str = query_time.strftime("%Y-%m-%d %H:%M:%S")
        is_updated, msg = self.compare_to_database()
        if not is_updated:
            return (False, [f"无更新数据。\n查询时间：{query_time_str}\n上次数据更新时间：{self.data['last_update_time']}",])
        messages = [f"检测到呼啦圈有{len(msg)}条数据更新\n查询时间：{query_time_str}"] + msg
        return (True, messages)
        

    # ---------------------静态函数--------------------- #
def get_display_width(s):
    width = 0
    for char in s:
        # 判断字符是否是全宽字符（通常是中文等）
        if unicodedata.east_asian_width(char) in ['F', 'W']:  # 'F' = Fullwidth, 'W' = Wide
            width += 3  # 全宽字符占用2个位置
        else:
            width += 1  # 半宽字符占用1个位置
    return width

def ljust_for_chinese(s, width, fillchar=' '):
    current_width = get_display_width(s)
    if current_width >= width:
        return s
    fill_width = width - current_width
    result = s + fillchar * fill_width
    return result

def standardize_datetime(dateAndTime):
    current_year = datetime.now().year
    if len(dateAndTime.split("-")[0]) != 4:
        dateAndTime = str(current_year) + "-" + dateAndTime
    try:
        dt = datetime.strptime(dateAndTime, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = datetime.strptime(dateAndTime, "%Y-%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d %H:%M")

def extract_city(address):
    city_pattern_1 = r'([^\s]{2})市'
    city_pattern_2 = r'([^\s]{4,})区'
    city_pattern_3 = r'([^\s]+省)'
    match = re.search(city_pattern_1, address)
    if match:
        return match.group(1)
    match = re.search(city_pattern_2, address)
    if match:
        return None

    match = re.search(city_pattern_3, address)
    if match:
        return match.group(1)[:-1]
    return None