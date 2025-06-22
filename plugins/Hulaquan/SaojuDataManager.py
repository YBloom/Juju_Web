import requests
import pandas as pd
from datetime import datetime, timedelta
from plugins.AdminPlugin.BaseDataManager import BaseDataManager

def dateToStr(date):
    if isinstance(date, datetime):
        return date.strftime("%Y-%m-%d")
    else:
        return date
    
def timeToStr(_time):
    if isinstance(_time, datetime):
        return _time.strftime("%H:%M")
    else:
        return _time

def strToDate(date="", time="", dateAndTime=""):
    # time "08:30"
        if dateAndTime or (date and time):
            if (date and time):
                dateAndTime = date + " " + time
            try:
            # 尝试解析包含秒数的格式
                return datetime.strptime(dateAndTime, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # 如果没有秒数，使用不包含秒数的格式
                return datetime.strptime(dateAndTime, "%Y-%m-%d %H:%M")
        elif date:
            return datetime.strptime(date, "%Y-%m-%d")
        elif time:
            return datetime.strptime(time, "%H:%M")
        else:
            return None
        
def delta_time_list(start_date, end_date):
        # 生成日期列表
        start_date = strToDate(date=start_date)
        end_date = strToDate(date=end_date)
        date_list = []
        current_date:datetime = start_date

        while current_date <= end_date:
            date_list.append(current_date)
            current_date += timedelta(days=1)
        return date_list   
    
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

def get_max_cast_length(casts=None):
    return 8
        
class SaojuDataManager(BaseDataManager):
    """
    功能：
    1.存储/调取卡司排期数据
    2.根据卡司数据有效期刷新
    """
    def __init__(self, file_path, file_type=None):
        file_path = file_path or "plugins/Hulaquan/saoju_data.json"
        super().__init__(file_path, file_type)

    def _check_data(self):
        self.data.setdefault("date_dict", {})  # 确保有一个日期字典来存储数据
        self.data.setdefault("update_time_dict", {})  # 确保有一个更新时间字典来存储数据
        self.data["update_time_dict"].setdefault("date_dict", {})  # 确保有一个更新时间字典来存储数据
        self.refresh_expired_data()

    def search_day(self, date):
        """
        "date": "2023-07-25"
        "show_list":
            "city": "X城市"
            "musical": "XX音乐剧"
            "theatre": "XX剧院"
            "time": "19:30"
            "cast":
            {"role": "A角色", "artist": "X演员"}
            {"role": "B角色", "artist": "Y演员"}
        """
        url = "http://y.saoju.net/yyj/api/search_day/"
        data = {"date": date}
        try:
            response = requests.get(url, params=data)
            response.raise_for_status()  # 如果响应状态码不是200，将抛出HTTPError异常
            json_response = response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f'SAOJU ERROR HTTP error occurred: {http_err}')  # 打印HTTP错误信息
        except Exception as err:
            print(f'SAOJU ERROR Other error occurred: {err}')  # 打印其他类型的错误信息
        return json_response
    
    def get_data_by_date(self, date, update_delta_max_hours=12):
        if date in self.data["date_dict"].keys():
            update_time = strToDate(self.data["update_time_dict"]["date_dict"].get(date, None))
            if (datetime.now() - update_time) < timedelta(hours=update_delta_max_hours):
                return self.data["date_dict"][date]
        else:
            data = self.search_day(date)
            if data:
                self.data["date_dict"][date] = data["show_list"]
                self.data["update_time_dict"]["date_dict"][date] = dateToStr(datetime.now())
                return data["show_list"]
            else:
                return None

    def search_for_musical_by_date(self, search_name, date_time, city=None):
        # date_time: %Y-%m-%d %H:%M
        date_time = strToDate(dateAndTime=date_time)
        _date = dateToStr(date_time)
        _time = timeToStr(date_time)
        data = self.get_data_by_date(_date)
        for i in range(len(data)):
            musical = data[i]["musical"]
            if ((city in data[i]["city"]) if city else True) and _time == data[i]["time"] and ((search_name in musical) if isinstance(search_name, str) else all(i in musical for i in search_name) if isinstance(search_name, list) else False):
                return data[i]
        return None
    
    def refresh_expired_data(self):
        """
        检查数据是否过期
        如果过期则刷新数据
        """
        current_date = datetime.now()
        for date in list(self.data.keys()):
            date_obj = strToDate(date=date)
            if date_obj < current_date:
                # 如果数据过期，删除该日期的数据
                del self.data[date]
                del self.data["update_time_dict"]["date_dict"][date]

    def search_for_artist(self, search_name, date):
        date = dateToStr(date)
        data = self.get_data_by_date(date)
        schedule = []
        for i in range(len(data)):
            for cast in data[i]["cast"]:
                if cast["artist"] == search_name:
                    schedule.append(data[i])
        return schedule

    def search_casts_by_date_and_name(self, name, date_time, city=None):
        """
        根据日期和剧名查询演出卡司
        :param date: str, 日期格式为 "YYYY-MM-DD HH:MM"
        :param name: str, 剧名
        :return: str 关于卡司的信息
        """
        date_time = standardize_datetime(date_time)
        response = self.search_for_musical_by_date(name, date_time, city)
        if not response:
            return []
        casts = [ljust_for_chinese(i["artist"], get_max_cast_length()) for i in response["cast"]]
        #casts = response["cast"]
        if not casts:
            return []
        return casts

    def search_artist_from_timetable(self, search_name, timetable: list[datetime]):
        """
        Args:
            search_name (_type_): str
            timetable (list[datetime]): [(2025,05,01),,]
        Return:
            schedule (list): [(datetime, dict), (datetime, dict)]
        [
            (datetime(2025, 5, 1), {"musical": "剧名", "time": "时间", "theatre": "剧场", "city": "城市", "cast": [{"role": "角色", "artist": "演员"}]})
        ]
        """
        schedule = []
        for date in timetable:
            show = self.search_for_artist(search_name, date)
            for i in show:
                show_date = dateToStr(date=date) + " " + i["time"]
                show_date = strToDate(dateAndTime=show_date)
                schedule.append((show_date, i))
        schedule.sort(key=lambda x: x[0])
        return schedule
        
    def check_artist_schedule(self, start_time, end_time, artist):
        #start_time = "2025-05-19"
        #end_time = "2025-06-30"
        #artist = "丁辰西"
        timetable = delta_time_list(start_time, end_time)
        schedule = self.search_artist_from_timetable(artist, timetable)
        data = []
        for event in schedule:
            date = event[0]
            info = event[1]
            data.append({
                '日期': date.strftime('%Y-%m-%d %H:%M'),
                '剧名': info['musical'],
                '时间': info['time'],
                '剧场': info['theatre'],
                '城市': info['city'],
                '卡司': " ".join([i["artist"] for i in info['cast']])
            })

        df = pd.DataFrame(data)
        s = "演员: {}".format(artist) + "\n" 
        + ("从{}到{}的排期".format(start_time, end_time)) 
        + "\n" + ("排期数量: {}".format(len(df)))
        + df.to_string(index=False, justify='left')
        return s
    
def match_artists_on_schedule(
    artists, 
    start_time, 
    end_time, 
    week_time_slots,  # [["20:00"], ["20:00"], ["20:00"], ["20:00"], ["20:00"], ["14:00","17:00", "20:00"], ["14:00","17:00", "20:00"]]
    min_gap_hours=4, 
    target_city="上海", 
    cross_city_gap_hours=15
):
    """
    week_time_slots: 长度为7的列表，每个元素为当天需要判断的时间点字符串列表（如["20:00"]或["14:00","17:00","20:00"]）
    min_gap_hours: 同城赶场所需最少小时数
    target_city: 目标演出城市
    cross_city_gap_hours: 跨城市赶场所需最少小时数
    """
    timetable = delta_time_list(start_time, end_time)
    # 构建每个演员的排期字典: {artist: {date: [(datetime, city)]}}
    artist_schedules = {}
    for artist in artists:
        schedule = search_artist_from_timetable(artist, timetable)
        daily_events = {}
        for show_time, info in schedule:
            date_str = dateToStr(date=show_time)
            city = info.get("city", "")
            if date_str not in daily_events:
                daily_events[date_str] = []
            daily_events[date_str].append((show_time, city))
        artist_schedules[artist] = daily_events

    free_slots = []
    for date in timetable:
        date_str = date.strftime("%Y-%m-%d")
        weekday = date.weekday()  # 0=周一, 6=周日
        for slot_time_str in week_time_slots[weekday]:
            slot_time = datetime.strptime(slot_time_str, "%H:%M").time()
            slot_dt = datetime.combine(date, slot_time)
            all_free = True
            for artist in artists:
                busy = False
                events = artist_schedules[artist].get(date_str, [])
                for event_time, event_city in events:
                    # 计算时间间隔
                    delta_hours = abs((slot_dt - event_time).total_seconds()) / 3600
                    if event_city == target_city:
                        need_gap = min_gap_hours
                    else:
                        need_gap = cross_city_gap_hours
                    if delta_hours < need_gap:
                        busy = True
                        break
                if busy:
                    all_free = False
                    break
            if all_free:
                free_slots.append({"日期": date_str, "时间": slot_time_str})

    df = pd.DataFrame(free_slots)
    if not df.empty:
        df = df.sort_values(by=["日期", "时间"]).reset_index(drop=True)
        # 增加“星期”列
        df["星期"] = df["日期"].apply(lambda x: ["一", "二", "三", "四", "五", "六", "日"][datetime.strptime(x, "%Y-%m-%d").weekday()])
        # 调整列顺序
        df = df[["日期", "星期", "时间"]]
    print("演员: {}".format(", ".join(artists)))
    print("所有演员都空闲的指定时间段日期：")
    print(df)
    
if __name__ == '__main__':
    #check_artist_schedule("2025-05-19", "2025-08-30", "丁辰西")
    #match_artists_on_schedule(["丁辰西", "陈玉婷", "郑涵一"], "2025-05-19", "2025-06-10")
    week_time_slots = [
        ["20:00"], ["20:00"], ["20:00"], ["20:00"], ["20:00"],  # 周一到周五
        ["14:00", "17:00", "20:00"], ["14:00", "17:00", "20:00"]  # 周六周日
    ]
    match_artists_on_schedule(
        ["丁辰西", "党韫葳", "邓贤凌"], 
        "2025-05-19", 
        "2025-06-10", 
        week_time_slots, 
        target_city="上海", 
    )