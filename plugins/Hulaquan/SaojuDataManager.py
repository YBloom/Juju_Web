if __name__ == '__main__':
    import os
    os.chdir("f:/MusicalBot/")
    import sys
    sys.path.append("f:/MusicalBot")
    

import aiohttp, asyncio, json
import pandas as pd
from datetime import datetime, timedelta
from plugins.Hulaquan import BaseDataManager
from plugins.Hulaquan.utils import *
import requests
from bs4 import BeautifulSoup

class SaojuDataManager(BaseDataManager):
    """
    功能：
    1.存储/调取卡司排期数据
    2.根据卡司数据有效期刷新
    """
    def __init__(self, file_path=None):
        super().__init__(file_path)

    def on_load(self):
        import importlib
        
        self.data.setdefault("date_dict", {})  # 确保有一个日期字典来存储数据
        self.data.setdefault("update_time_dict", {})  # 确保有一个更新时间字典来存储数据
        self.data["update_time_dict"].setdefault("date_dict", {})  # 确保有一个更新时间字典来存储数据
        self.refresh_expired_data()

    async def search_day_async(self, date):
        url = "http://y.saoju.net/yyj/api/search_day/"
        data = {"date": date}
        max_retries = 5
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=data, timeout=10) as response:
                        response.raise_for_status()
                        json_response = await response.json()
                        return json_response
            except aiohttp.ClientError as http_err:
                print(f'SAOJU ERROR HTTP error occurred (attempt {attempt+1}): {http_err}')
            except Exception as err:
                print(f'SAOJU ERROR Other error occurred (attempt {attempt+1}): {err}')
            await asyncio.sleep(1)  # 每次失败后等待1秒再重试
        print('SAOJU ERROR: Failed to fetch data after 5 attempts.')
        return

    async def get_data_by_date_async(self, date, update_delta_max_hours=1):
        if date in list(self.data["date_dict"].keys()):
            update_time = parse_datetime(self.data["update_time_dict"]["date_dict"].get(date, None))
            if update_time:
                if (datetime.now() - update_time) < timedelta(hours=update_delta_max_hours):
                    return self.data["date_dict"][date]
        data = await self.search_day_async(date)
        if data:
            self.data["date_dict"][date] = data["show_list"]
            self.data["update_time_dict"]["date_dict"][date] = dateTimeToStr(datetime.now())
            return data["show_list"]
        else:
            return None


    async def search_for_musical_by_date_async(self, search_name, date_time, city=None):
        # date_time: %Y-%m-%d %H:%M
        date_time = parse_datetime(date_time)
        _date = dateToStr(date_time)
        _time = timeToStr(date_time)
        data = await self.get_data_by_date_async(_date)
        if not data:
            return None
        for i in range(len(data)):
            musical = data[i]["musical"]
            if ((city in data[i]["city"]) if city else True) and _time == data[i]["time"] and ((search_name in musical) if isinstance(search_name, str) else all(i in musical for i in search_name) if isinstance(search_name, list) else False):
                return data[i]
        return None

    def refresh_expired_data(self):
        current_date = datetime.now()
        for date in list(self.data["update_time_dict"]["date_dict"].keys()):
            date_obj = parse_datetime(date)
            if date_obj < current_date:
                del self.data["date_dict"][date]
                del self.data["update_time_dict"]["date_dict"][date]

    async def search_for_artist_async(self, search_name, date):
        date = dateToStr(date)
        data = await self.get_data_by_date_async(date)
        schedule = []
        if not data:
            return schedule
        for i in range(len(data)):
            for cast in data[i]["cast"]:
                if cast["artist"] == search_name:
                    schedule.append(data[i])
        return schedule

    async def search_artist_from_timetable_async(self, search_name, timetable: list):
        schedule = []
        for date in timetable:
            show = await self.search_for_artist_async(search_name, date)
            for i in show:
                show_date = dateToStr(date=date) + " " + i["time"]
                show_date = parse_datetime(show_date)
                schedule.append((show_date, i))
        schedule.sort(key=lambda x: x[0])
        return schedule

    async def check_artist_schedule_async(self, start_time, end_time, artist):
        timetable = delta_time_list(start_time, end_time)
        schedule = await self.search_artist_from_timetable_async(artist, timetable)
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
        s = "演员: {}".format(artist) + "\n" \
            + ("从{}到{}的排期".format(start_time, end_time)) \
            + "\n"
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
    
    
            
    async def get_artist_events_data(self, cast_name):
        updated = False
        try:
            if 'artists_map' not in self.data or cast_name not in self.data['artists_map']:
                self.data['artists_map'] = await self.fetch_saoju_artist_list()
                updated = True
        except:
            self.data['artists_map'] = await self.fetch_saoju_artist_list()
            updated = True
        if updated and cast_name not in self.data['artists_map']:
            return False
        else:
            pk = self.data['artists_map'][cast_name]
        html_data = await fetch_page_async(f"http://y.saoju.net/yyj/artist/{pk}/?other=1&musical=")
        events = self.parse_artist_html(html_data)
        return events
    
    async def match_co_casts(self, co_casts: list, show_others=True, return_data=False):
        search_name = co_casts[0]
        _co_casts = co_casts[1:]
        events = await self.get_artist_events_data(search_name)
        result = []
        latest = ""
        for event in events:
            others = event['others'].split(" ")
            if all(cast in others for cast in _co_casts): 
                others = [item for item in others if item not in _co_casts]
                dt = event['date']
                event['date'] = standardize_datetime_for_saoju(dt, return_str=True, latest_str=latest)
                latest = dt
                result.append(event)
        if return_data:
            return result
        else:
            return self.generate_co_casts_message(co_casts, show_others, result)

    def generate_co_casts_message(self, co_casts, show_others, co_casts_data):
        messages = []
        messages.append(" ".join(co_casts)+f"同场的音乐剧演出，目前有{len(co_casts_data)}场。")
        for event in co_casts_data:
            if show_others:
                event['others'] = "\n同场其他演员：" + " ".join(event['others'])
            else:
                event['others'] = ""
            messages.append(f"{event['date']} {event['city']} {event['title']}{event['others']}")
        return messages

    async def request_co_casts_data(self, co_casts: list, show_others=False):
        return self.match_co_casts(co_casts, show_others, return_data=True)
        
    
    async def fetch_saoju_artist_list(self):
        data = json.loads(await fetch_page_async("http://y.saoju.net/yyj/api/artist/"))
        name_to_pk = {item["fields"]["name"]: item["pk"] for item in data}
        return name_to_pk

    # 解析网页内容
    def parse_artist_html(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', class_='ui striped celled pink unstackable compact table')
        
        if not table:
            return []
        musicals = []
        for row in table.find_all('tr')[1:]:  # 跳过表头
            cols = row.find_all('td')
            
            if len(cols) < 5:
                continue  # 如果列数不对，跳过这一行
            
            date = re.sub(r'\s+', ' ', cols[0].text.strip().replace("\n", ""))
            title = cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip()
            role = cols[2].text.strip()
            others = " ".join([a.text.strip() for a in cols[3].find_all('a')])
            city = cols[4].find_all('a')[0].text.strip() if cols[4].find_all('a') else ''
            location = cols[4].find_all('a')[1].text.strip() if len(cols[4].find_all('a')) > 1 else ''
            
            musical_data = {
                'date': date,
                'title': title,
                'role': role,
                'others': others,
                'city': city,
                'location': location
            }
            
            musicals.append(musical_data)

        return musicals

    
    
async def fetch_page_async(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()    
    
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

if __name__ == "__main__":
    import asyncio
    async def test_match_co_casts():
        manager = SaojuDataManager()
        # 示例演员列表，替换为实际存在的演员名
        co_casts = ["丁辰西", "陈玉婷"]
        messages = await manager.match_co_casts(co_casts, show_others=True)
        for msg in messages:
            print(msg)
    asyncio.run(test_match_co_casts())
