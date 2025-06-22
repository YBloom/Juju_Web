from datetime import datetime
import unicodedata
from plugins.Hulaquan.SaojuDataManager import SaojuDataManager
import requests
import re
import json
from plugins.AdminPlugin.BaseDataManager import BaseDataManager

class HulaquanDataManager(BaseDataManager):
    """
    功能：
    1.存储/调取卡司排期数据
    2.根据卡司数据有效期刷新
    """
    def __init__(self, file_path=None, file_type=None):
        file_path = file_path or "plugins/Hulaquan/hulaquan_events_data.json"
        super().__init__(file_path, file_type)
        self.data.setdefault("events", {})  # 确保有一个事件字典来存储数据

    def update_data(self):
        """更新数据

        Returns:
            返回(old_data, new_data)
        """
        old_data = self.data
        self.data = self.dump_hulaquan_events_data()
        return old_data, self.data

    def get_recommendation(self, limit=12, page=0, timeMark=True, tags=None):
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

    def dump_hulaquan_events_data(self, data_dict=None):
        try:
            self.data = data_dict or self.get_events_dict()
            return data_dict
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
        data = self.get_all_events()
        data_dict = {}
        for event in data:
            event_id = str(event["id"])
            if event_id not in data_dict:
                data_dict[event_id] = event
        data_dic = {}
        data_dic["events"] = data_dict
        data_dic["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return data_dic

    def get_all_events(self):
        count = self.get_recommendation(1,0,False)[0]  # Test the connection and the count
        #print(f"Total recommendations available: {count}")
        data = []
        data += self.get_recommendation(count//4, 0, True)[1]
        return data

    def search_eventID_by_name(self, event_name):
        data = self.data["events"]
        result = []
        for eid, event in data.items():
            title = event["title"]
            if re.search(event_name, title, re.IGNORECASE):
                result.append([eid, title])
        return result
        
    def search_event_by_id(self, event_id):
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
        old_data = self.data["events"]
        for eid, event in old_data.items():
            print(eid, event["title"], event["end_time"], event["update_time"])
        
    # ------------------------------------------ #


    def get_max_ticket_content_length(self, tickets):
        max_len = 0
        for ticket in tickets:
            s = "{ticket[0]} 余票{ticket[2]}/{ticket[1]}"
            max_len = max(max_len, get_display_width(s))
        return max_len

    # -------------------Query------------------------------ #         
    # ---------------------Announcement--------------------- #

    def compare_to_database(self, __dump=True):
        # 将新爬的数据与旧数据进行比较，找出需要更新的数据
        """
        __dump: bool, 是否将新数据写入文件
        Returns:
            update_data: list, 包含需要更新的事件数据
            None: 如果没有需要更新的数据
        """
        update_data = []
        if not __dump:
            new_data_all = self.get_events_dict()
            old_data_all = self.data
        else:
            old_data_all, new_data_all = self.update_data()
        new_data = new_data_all["events"]
        old_data, update_time = old_data_all["events"], old_data_all["update_time"]
        for eid, event in new_data.items():
            if eid not in old_data.keys():
                update_data.append(event)
            else:
                old_event = old_data[eid]
                if event["end_time"] != old_event["end_time"] or event["update_time"] != old_event["update_time"]:
                    update_data.append(event)
        if update_data:
            return True, update_data
        else:
            return False, update_time
        
    def message_tickets_query(self, eName, saoju, ignore_sold_out=False, show_cast=True):
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
        event_data = self.search_event_by_id(eid)
        if event_data:
            event_info = event_data["basic_info"]
            title = event_info.get("title", "未知剧名")
            tickets_details = event_data.get("ticket_details", [])
            remaining_tickets = []
            for ticket in tickets_details:
                if datetime.strptime(ticket["start_time"], "%Y-%m-%d %H:%M:%S") > datetime.now():
                    if ticket["left_ticket_count"] > (0 if ignore_sold_out else -1):
                        remaining_tickets.append([ticket["title"], ticket["total_ticket"], ticket["left_ticket_count"], ticket["start_time"]])
            max_ticket_info_count = self.get_max_ticket_content_length(remaining_tickets)
            query_time_str = query_time.strftime("%Y-%m-%d %H:%M:%S")
            message = (
                f"剧名: {title}\n"
                f"数据更新时间: {query_time_str}\n"
                "剩余票务信息:\n"
                + "\n".join([("✨" if ticket[2] else "❌") 
                                + ljust_for_chinese(f"{ticket[0]} 余票{ticket[2]}/{ticket[1]}", max_ticket_info_count)
                                + (" " + (" ".join(saoju.search_casts_by_date_and_name(eName, 
                                                                                ticket[3], 
                                                                                city=extract_city(event_info.get("location", ""))
                                                                                )
                                                )
                                        )
                                ) if show_cast else ""
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
        is_updated, update_data = self.compare_to_database(__dump=True)
        if not is_updated:
            return (False, [f"无更新数据。\n查询时间：{query_time_str}\n上次数据更新时间：{update_data}",])
        messages = [f"检测到呼啦圈有{len(update_data)}条数据更新\n查询时间：{query_time_str}"]
        for i in update_data:
            message = (
                f"剧名: {i['title']}\n"
                f"活动结束时间: {i['end_time']}\n"
                f"更新时间: {i['update_time']}\n"
            )
            messages.append(message)
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
    return s + fillchar * fill_width

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