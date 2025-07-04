from datetime import datetime, timedelta
import unicodedata
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

def dateTimeToStr(_time):
    if isinstance(_time, datetime):
        return _time.strftime("%Y-%m-%d %H:%M")
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

def get_max_cast_length(casts=None):
    return 8

def standardize_datetime(dateAndTime: str, return_str=True, with_second=True):
    # 当前年份
    current_year = datetime.now().year
    dateAndTime = dateAndTime.replace("：", ':')
    
    # 尝试不同的日期时间格式
    formats = [
        "%Y-%m-%d %H:%M",  # 2025-12-07 06:30
        "%m-%d %H:%M",     # 12-07 06:30
        "%m-%d %H:%M:%S",  # 12-07 06:30:21
        "%y-%m-%d %H:%M",  # 25-12-07 06:30
        "%y/%m/%d %H:%M",   # 25/12/07 06:30
        "%Y-%m-%d",           # 格式: 年-月-日
        "%H:%M",              # 格式: 时:分
        "%H:%M:%S",            # 格式: 时:分:秒
        
    ]
    for fmt in formats:
        try:
            # 如果年份不在字符串中, 默认使用当前年份
            if fmt[0] == "%y" or fmt[0] == "%Y":
                if dateAndTime[:2].isdigit() and len(dateAndTime.split()[0]) == 7:  # "25/12/07"
                    dateAndTime = str(current_year) + "-" + dateAndTime
                dt = datetime.strptime(dateAndTime, fmt)
            else:
                dt = datetime.strptime(dateAndTime, fmt)
            if len(str(dt.second)) == 0:
                dt = dt.replace(second=0)
            if return_str:
                if with_second:
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    return dt.strftime("%Y-%m-%d %H:%M")
            else:
                return dt
        except ValueError:
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

def extract_text_in_brackets(text):
    # 正则表达式匹配《xxx》
    match = re.search(r'《(.*?)》', text)
    if match:
        return match.group(0)  # 返回整个《xxx》内容
    return None  # 如果没有匹配到，返回None

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