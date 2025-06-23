from datetime import datetime
import unicodedata
from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
import requests
import re
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
            self.data["update_time"] = data_dict["update_time"]
            return self.data
        except Exception as e:
            print(f"呼啦圈数据下载失败: {e}")
            return None

    def get_events_dict(self):
        """
        Generate a dictionary of events from the recommendation API.
        datadict: {event_id: event_info}
        event_info: {"3848": {
            "id": 3848,
            "title": "原创环境式音乐剧《流星之绊》改编自东野圭吾同名小说",
            "location": "上海市黄浦区西藏南路1号大世界4楼E厅（上海大世界·星空间10号·MOriginal Box）",
            "start_time": "2025-05-01 19:30:00",
            "end_time": "2025-06-30 21:30:00",
            "deadline": "2025-06-30 21:30:00",
            "all_day_event": null,
            "rich_description": "<h4 style=\"text-wrap: wrap; border-bottom: 1px solid rgb(187, 187, 187); border-right: 1px solid rgb(187, 187, 187); color: rgb(51, 51, 51); font-family: 黑体; letter-spacing: 1px; line-height: 24px; background-color: rgb(238, 238, 238); font-size: 14px; padding-left: 6px; margin: 15px 0px;\">购票须知</h4><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51); text-align: center;\"><span style=\"color: rgb(192, 0, 0);\"><strong><span style=\"text-align: justify;\">学生票盲盒</span></strong></span></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51); text-align: center;\"><span style=\"color: rgb(192, 0, 0);\"><strong><span style=\"text-align: justify;\">199元(399~499座位随机)</span></strong></span></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51);\"><span style=\"text-align: justify;\">【购票方式】点击活动下方的对应的时间场次图标可按提示购票。请下载呼啦圈APP收到演出通知和提醒。</span></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51);\"><span style=\"text-align: justify;\"><span style=\"color: rgb(192, 0, 0); font-family: 微软雅黑, 宋体; font-size: 13px; letter-spacing: 1px; text-align: justify; text-wrap: wrap;\">票品为有价证券，非普通商品，其后承载的文化服务具有时效性，稀缺性等特征，不支持退换。购票时请勿仔细核对相关信息并谨慎下单。</span></span></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51); text-align: justify;\">【取票规则】<strong><span style=\"color: rgb(118, 146, 60);\">学生票</span></strong>: 演出当天提前一小时，凭学生证至上海市黄浦区西藏南路1号大世界4楼E厅（上海大世界·星空间10号·MOriginal Box）取票处实名取票及入场，人证票一致方可入场。。<strong>学生票禁止转让，仅限购票本人使用。</strong></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51); text-align: justify;\">【咨询电话】4008781318, 小呼啦微信:hulacampus<a href=\"https://weibo.com/7741472507\" target=\"_self\"><strong style=\"text-align: center; color: rgb(192, 0, 0);\"><span style=\"text-align: justify;\"><img src=\"http://lift.cloudsation.com/meetup/detail/1861640866230308864.jpg\" title=\"\" alt=\"微信图片_20241127131538.jpg\" width=\"70\" height=\"54\" style=\"width: 70px; height: 54px; float: right;\"/></span></strong></a><span style=\"font-size: 13px;\"><br/></span></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51); text-align: justify;\"><span style=\"font-size: 13px;\">【异常订购说明】</span><span style=\"font-size: 13px;\"></span></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51); text-align: justify;\"><span style=\"font-size: 13px;\">对于异常订购行为，呼啦圈有权在订单成立或者生效之后取消相应订单。异常订购行为包括但不限于以下情形： （1）通过同一ID订购超出限购张数的订单； （2）经合理判断认为非真实消费者的下单行为，包括但不限于通过批量相同或虚构的支付账号、收货地址（包括下单时填写及最终实际收货地址）、收件人、电话号码订购超出限购张数的订单</span></p><p style=\"text-wrap: wrap; font-family: 微软雅黑, 宋体; letter-spacing: 1px; line-height: 28px; font-size: 14px; color: rgb(51, 51, 51); text-align: justify;\"><span style=\"font-size: 13px;\"><strong style=\"color: rgb(74, 74, 74); font-family: 微软雅黑;\"></strong><strong style=\"color: rgb(74, 74, 74); font-family: 微软雅黑;\">入场温馨提示</strong><br/>入场时，请听从现场工作人员的引导指示，保持一米以上间隔有序入场，场内严禁饮食，感谢您的支持与配合，祝您观演愉快！</span><span style=\"font-size: 13px;\">因个人原因导致无法入场，将不做退换票处理，敬请谅解！</span></p><h4 style=\"text-wrap: wrap; border-bottom: 1px solid rgb(187, 187, 187); border-right: 1px solid rgb(187, 187, 187); color: rgb(51, 51, 51); font-family: 黑体; letter-spacing: 1px; line-height: 24px; background-color: rgb(238, 238, 238); font-size: 14px; padding-left: 6px; margin: 15px 0px;\">演出介绍</h4><p style=\"text-align: center;\"><img src=\"http://lift.cloudsation.com/meetup/detail/1902573448199278592.jpg\" title=\"\" alt=\"1.jpg\" style=\"width: 100%;\"/><img src=\"http://lift.cloudsation.com/meetup/detail/1902573478154997760.jpg\" title=\"\" alt=\"2.jpg\" style=\"width: 100%;\"/><img src=\"http://lift.cloudsation.com/meetup/detail/1902573508114911232.jpg\" title=\"\" alt=\"3.jpg\" style=\"width: 100%;\"/><img src=\"http://lift.cloudsation.com/meetup/detail/1902573537902858240.jpg\" title=\"\" alt=\"4.jpg\" style=\"width: 100%;\"/><img src=\"http://lift.cloudsation.com/meetup/detail/1902573568303173632.jpg\" title=\"\" alt=\"5.jpg\" style=\"width: 100%;\"/><img src=\"http://lift.cloudsation.com/meetup/detail/1902573597822685184.jpg\" title=\"\" alt=\"6.jpg\" style=\"width: 100%;\"/><img src=\"http://lift.cloudsation.com/meetup/detail/1902573624242606080.jpg\" title=\"\" alt=\"7.jpg\" style=\"width: 100%;\"/><img src=\"http://lift.cloudsation.com/meetup/detail/1902573657746706432.jpg\" title=\"\" alt=\"8.jpg\" style=\"width: 100%;\"/></p>",
            "description": "",
            "description_url": null,
            "organizer": 81460,
            "status": "processing",
            "directory": null,
            "min_people": null,
            "max_people": 1000,
            "type": "public",
            "create_time": "2025-03-17 14:28:16",
            "contact": "4008781318",
            "location_id": null,
            "update_time": "2025-05-14 15:26:22",
            "phone_required": false,
            "verify_required": false,
            "verify_detail": null,
            "sponsor": null,
            "sponsor_url": null,
            "view_count": 20199,
            "show_qr_code": 1}
        Returns:
            _type_: _description_
        """
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

    def search_ticket_details(self, event_id):
        json_data = self.search_event_by_id(event_id)
        keys_to_extract = ["id","event_id","title", "start_time", "end_time","status","create_time","ticket_price","total_ticket", "left_ticket_count", "left_days"]
        json_data: list = json_data["ticket_details"]
        for i in range(len(json_data)):
            json_data[i] = {key: json_data[i].get(key, None) for key in keys_to_extract}
        return json_data
        
    def get_ticket_details(self, event_id):
        if not self.data["events"][event_id].get("ticket_details", None):
            self._update_ticket_details(event_id)
        return self.data["events"][event_id]
    
    def _update_ticket_details(self, event_id):
        self.data["events"][event_id]["ticket_details"] = self.search_ticket_details(event_id)
        
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
                    message.append(f"🟢新开票场次：{'\n '.join(new_message)}")
                if return_message:
                    message.append(f"🟢回流（？）场次：{'\n '.join(return_message)}")
                if add_message:
                    message.append(f"🟢补票场次：{'\n '.join(add_message)}")
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
        if not old_data or not new_data:
            return new_data
        old_data_dict = {item['id']: item for item in old_data}
        update_data = []

        # 遍历 new_data 并根据条件进行更新
        for new_item in new_data:
            new_id = new_item['id']
            new_left_ticket_counts = new_item['left_ticket_counts']
            new_total_ticket = new_item['total_ticket']

            if new_id not in old_data_dict:
                # 如果 new_data 中存在新的 id，则标记为 "new"
                new_item['update_status'] = 'new'
                update_data.append(new_item)
            else:
                # 获取 old_data 中对应 id 的旧数据
                old_item = old_data_dict[new_id]
                old_left_ticket_counts = old_item['left_ticket_counts']
                old_total_ticket = old_item['total_ticket']
                if new_total_ticket > old_total_ticket:
                    # 如果 total_ticket 增加了，则标记为 "add"
                    new_item['update_status'] = 'add'
                    update_data.append(new_item)
                elif new_left_ticket_counts > old_left_ticket_counts:
                    # 如果 left_ticket_counts 增加了，则标记为 "return"
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
        event_data = self.data[eid]
        if event_data:
            title = event_data.get("title", "未知剧名")
            tickets_details = event_data.get("ticket_details", [])
            remaining_tickets = []
            for ticket in tickets_details:
                if ticket["status"] == "active":
                    if ticket["left_ticket_count"] > (0 if ignore_sold_out else -1):
                        remaining_tickets.append(ticket)
            max_ticket_info_count = self.get_max_ticket_content_length(remaining_tickets)
            query_time_str = query_time.strftime("%Y-%m-%d %H:%M:%S")
            url = f"https://clubz.cloudsation.com/event/{eid}.html"
            message = (
                f"剧名: {title}\n"
                f"数据更新时间: {query_time_str}\n"
                f"购票链接：{url}\n"
                "剩余票务信息:\n"
                + "\n".join([("✨" if ticket['left_ticket_count'] > 0 else "❌") 
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
                if remaining_tickets else "暂无剩余票务信息。"
                                )
            now_time = datetime.now()
            delta_time = now_time - query_time
            message += f"\n⌚耗时: {delta_time.total_seconds():.2f}秒⌚"
            return message
        else:
            return "未找到该剧目的详细信息。"
        
    def message_update_data(self):
        # Return: (is_updated: bool, messages: [list:Str])
        query_time = datetime.now()
        query_time_str = query_time.strftime("%Y-%m-%d %H:%M:%S")
        is_updated, msg = self.compare_to_database()
        if not is_updated:
            return (False, [f"无更新数据。\n查询时间：{query_time_str}\n上次数据更新时间：{update_data}",])
        messages = [f"检测到呼啦圈有{len(msg)}条数据更新\n查询时间：{query_time_str}"]
        messages.extend(msg)
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