from datetime import datetime, timedelta
import unicodedata
import traceback
import random
import re

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

def dateTimeToStr(_time, with_second=False):
    if isinstance(_time, datetime):
        return _time.strftime("%Y-%m-%d %H:%M") if not with_second else _time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return _time

def parse_datetime(dateAndTime):
    return standardize_datetime(dateAndTime, return_str=False)
   
def delta_time_list(start_date, end_date):
        # 生成日期列表
        start_date = parse_datetime(start_date)
        end_date = parse_datetime(end_date)
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
        if unicodedata.east_asian_width(char) in ['F', 'W'] or char in ["《", "》"]:  # 'F' = Fullwidth, 'W' = Wide
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

def get_max_cast_length(casts=None):
    return 8

def standardize_datetime_for_saoju(dateAndTime: str, return_str=False, latest_str: str=None):
    # 匹配“8月3日 星期日 14:30”
    match = re.match(r"(\d{1,2})月(\d{1,2})日.*?(\d{1,2}:\d{2})", dateAndTime)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        time_str = match.group(3)
        current_year = datetime.now().year
        dt_str = f"{current_year}-{month:02d}-{day:02d} {time_str}"
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            if return_str:
                # 返回原始格式（如“8月3日 星期日 14:30”）
                return dateAndTime
            else:
                return dt
        except Exception:
            pass

    # 匹配只有时间（如“14:30”），结合 latest_str 补全日期
    match_time = re.match(r"^(\d{1,2}:\d{2})$", dateAndTime)
    if match_time and latest_str:
        # 捕获星期几
        match_latest = re.match(r"(\d{1,2})月(\d{1,2})日\s*(星期[一二三四五六日天])?.*?(\d{1,2}:\d{2})", latest_str)
        if match_latest:
            month = int(match_latest.group(1))
            day = int(match_latest.group(2))
            weekday = match_latest.group(3) or ""
            time_str = match_time.group(1)
            current_year = datetime.now().year
            dt_str = f"{current_year}-{month:02d}-{day:02d} {time_str}"
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                if return_str:
                    # 拼接星期几
                    return f"{month}月{day}日 {weekday} {time_str}".strip()
                else:
                    return dt
            except Exception:
                pass
        else:
            raise KeyError(f"无法解析类型：{dateAndTime}")



def standardize_datetime(dateAndTime: str, return_str=True, with_second=True):
    current_year = datetime.now().year
    dateAndTime = dateAndTime.replace("：", ':').replace("/", "-").strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m-%d %H:%M:%S",
        "%m-%d %H:%M",
        "%m-%d",
        "%y-%m-%d %H:%M:%S",
        "%y-%m-%d %H:%M",
        "%H:%M:%S",
        "%H:%M",
        # 新增支持“2025 04-01 19:30”/“2025 04-01 19:30:00”格式
        "%Y %m-%d %H:%M:%S",
        "%Y %m-%d %H:%M",
    ]
    # 处理“8月3日 星期日 14:30”格式
    
    # 其他格式
    for fmt in formats:
        try:
            dt_str = dateAndTime
            fmt_try = fmt
            # 补全逻辑
            # 只时间
            if fmt_try.startswith("%H"):
                dt_str = f"{current_year}-01-01 {dt_str}"
                fmt_try = "%Y-%m-%d " + fmt_try
            # 只日期
            if fmt_try in ["%m-%d", "%y-%m-%d", "%Y-%m-%d"]:
                dt_str = f"{dt_str} 00:00:00"
                fmt_try = fmt_try + " %H:%M:%S"
            # 月日格式补全年份
            if fmt_try.startswith("%m-"):
                dt_str = f"{current_year}-{dateAndTime}"
                fmt_try = "%Y-" + fmt
            # 年月日+时分
            if fmt_try in ["%Y-%m-%d %H:%M", "%y-%m-%d %H:%M", "%m-%d %H:%M"]:
                if len(dt_str.split()) == 1:
                    dt_str = f"{dt_str} 00:00"
            # 年月日+时分秒
            if fmt_try in ["%Y-%m-%d %H:%M:%S", "%y-%m-%d %H:%M:%S", "%m-%d %H:%M:%S"]:
                if len(dt_str.split()) == 1:
                    dt_str = f"{dt_str} 00:00:00"
            dt = datetime.strptime(dt_str, fmt_try)
            if return_str:
                if with_second:
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    return dt.strftime("%Y-%m-%d %H:%M")
            else:
                return dt
        except Exception:
            continue
    raise ValueError("无法解析该日期时间格式")
        

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

def extract_text_in_brackets(text, keep_brackets=True):
    """
    提取《xxx》内容。
    keep_brackets=True: 返回《xxx》
    keep_brackets=False: 返回xxx
    没有书名号则返回原文
    """
    match = re.search(r'《(.*?)》', text)
    if match:
        return match.group(0) if keep_brackets else match.group(1)
    return text if not keep_brackets else "《"+text+"》"

def extract_title_info(text):
    # 正则表达式提取《xxx》，价格和原价
    price_match = re.findall(r'￥(\d+)', text)  # 匹配所有的￥金额

    title = extract_text_in_brackets(text)

    if price_match:
        # 获取价格列表中的金额
        price_values = [int(price) for price in price_match]

        # 如果有两个金额，选择最小的为price，另一个为full_price
        if len(price_values) == 2:
            price = min(price_values)
            full_price = max(price_values)
        elif len(price_values) == 1:
            price = price_values[0]
            full_price = None
        else:
            price = full_price = None
    else:
        price = full_price = None

    return {
        'title': title,
        'price': f'￥{price}' if price is not None else None,
        'full_price': f'￥{full_price}' if full_price is not None else None
    }
    
def now_time_str():
    return datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")

def parse_text_to_dict(text, with_prefix=True):
    text = text.replace("：", ":")
    lines = text.strip().split('\n')
    result = {}
    
    # 第一行是prefix
    if with_prefix:
        result['prefix'] = lines[0]
        lines = lines[1:]
    
    # 处理后面的行
    for line in lines:
        key, value = line.split(':', 1)
        result[key.strip()] = value.strip()
    
    return result

def parse_text_to_dict_with_mandatory_check(text, input_dict, with_prefix=True):
    parsed_data = parse_text_to_dict(text, with_prefix)
    result = {}
    mandatory_missing = []
    for field, info in input_dict.items():
        name = info["name"]
        mandatory = info["mandatory"]
        if field in parsed_data:
            result[name] = parsed_data[field]
        else:
            result[name] = None
            if mandatory:
                mandatory_missing.append(field)
    
    # 返回最终结果
    return result, mandatory_missing

def random_id(lens, id_list):
    end = 10 ** lens - 1
    start = 10 ** (lens-1)
    r_id = random.randint(start, end)
    while r_id in id_list:
        r_id = random.randint(start, end)
    return r_id
