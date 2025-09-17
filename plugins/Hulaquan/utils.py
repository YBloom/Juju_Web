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

# 将城市列表定义为模块级别的常量，避免每次调用都重新创建
# 按长度从大到小排序，优先匹配长的城市名（避免"北京"匹配到"北"）
CITIES = sorted([
    '北京', '上海', '天津', '重庆',
    '广州', '深圳', '珠海', '汕头', '佛山', '韶关', '湛江', '肇庆', '江门', '茂名', '惠州', '梅州', '汕尾', '河源', '阳江', '清远', '东莞', '中山', '潮州', '揭阳', '云浮',
    '南京', '无锡', '徐州', '常州', '苏州', '南通', '连云港', '淮安', '盐城', '扬州', '镇江', '泰州', '宿迁',
    '杭州', '宁波', '温州', '嘉兴', '湖州', '绍兴', '金华', '衢州', '舟山', '台州', '丽水',
    '合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城',
    '福州', '厦门', '莆田', '三明', '泉州', '漳州', '南平', '龙岩', '宁德',
    '南昌', '景德镇', '萍乡', '九江', '新余', '鹰潭', '赣州', '吉安', '宜春', '抚州', '上饶',
    '济南', '青岛', '淄博', '枣庄', '东营', '烟台', '潍坊', '济宁', '泰安', '威海', '日照', '临沂', '德州', '聊城', '滨州', '菏泽',
    '郑州', '开封', '洛阳', '平顶山', '安阳', '鹤壁', '新乡', '焦作', '濮阳', '许昌', '漯河', '三门峡', '南阳', '商丘', '信阳', '周口', '驻马店',
    '武汉', '黄石', '十堰', '宜昌', '襄阳', '鄂州', '荆门', '孝感', '荆州', '黄冈', '咸宁', '随州',
    '长沙', '株洲', '湘潭', '衡阳', '邵阳', '岳阳', '常德', '张家界', '益阳', '郴州', '永州', '怀化', '娄底',
    '成都', '自贡', '攀枝花', '泸州', '德阳', '绵阳', '广元', '遂宁', '内江', '乐山', '南充', '眉山', '宜宾', '广安', '达州', '雅安', '巴中', '资阳',
    '贵阳', '六盘水', '遵义', '安顺', '毕节', '铜仁',
    '昆明', '曲靖', '玉溪', '保山', '昭通', '丽江', '普洱', '临沧',
    '西安', '铜川', '宝鸡', '咸阳', '渭南', '延安', '汉中', '榆林', '安康', '商洛',
    '兰州', '嘉峪关', '金昌', '白银', '天水', '武威', '张掖', '平凉', '酒泉', '庆阳', '定西', '陇南',
    '西宁', '海东',
    '银川', '石嘴山', '吴忠', '固原', '中卫',
    '乌鲁木齐', '克拉玛依', '吐鲁番', '哈密',
    '拉萨', '日喀则',
    '呼和浩特', '包头', '乌海', '赤峰', '通辽', '鄂尔多斯', '呼伦贝尔', '巴彦淖尔', '乌兰察布',
    '沈阳', '大连', '鞍山', '抚顺', '本溪', '丹东', '锦州', '营口', '阜新', '辽阳', '盘锦', '铁岭', '朝阳', '葫芦岛',
    '长春', '吉林', '四平', '辽源', '通化', '白山', '松原', '白城',
    '哈尔滨', '齐齐哈尔', '鸡西', '鹤岗', '双鸭山', '大庆', '伊春', '佳木斯', '七台河', '牡丹江', '黑河', '绥化',
    '石家庄', '唐山', '秦皇岛', '邯郸', '邢台', '保定', '张家口', '承德', '沧州', '廊坊', '衡水',
    '太原', '大同', '阳泉', '长治', '晋城', '朔州', '晋中', '运城', '忻州', '临汾', '吕梁',
    '海口', '三亚', '三沙', '儋州',
    '南宁', '柳州', '桂林', '梧州', '北海', '防城港', '钦州', '贵港', '玉林', '百色', '贺州', '河池', '来宾', '崇左'
], key=len, reverse=True)

# 将城市列表转换为集合，提高查找效率 O(1)
CITIES_SET = set(CITIES)

# 预编译正则表达式，避免每次调用都重新编译
CITY_PATTERN = re.compile('|'.join(re.escape(city) for city in CITIES))

def detect_city_in_text(text):
    """
    在给定的文本中检测城市名称
    
    Args:
        text (str): 要检测的文本
        
    Returns:
        str or None: 检测到的第一个城市名称，如果没有检测到则返回None
        
    时间复杂度: O(m)，其中m是文本长度
    空间复杂度: O(1)
    """
    if not text:
        return None
        
    # 使用预编译的正则表达式进行匹配
    city_match = CITY_PATTERN.search(text)
    return city_match.group(0) if city_match else None

def extract_title_info(text):
    
    # 正则表达式提取《xxx》，价格和原价
    price_match = re.findall(r'￥(\d+)', text)  # 匹配所有的￥金额

    title = extract_text_in_brackets(text)
    
    # 提取书名号外的文本来检测城市
    text_outside_brackets = text
    brackets_match = re.search(r'《.*?》', text)
    if brackets_match:
        # 移除书名号内容，只保留书名号外的文本
        text_outside_brackets = text.replace(brackets_match.group(0), '')
    
    # 使用独立的城市检测函数
    detected_city = detect_city_in_text(text_outside_brackets)
    
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

    result = {
        'title': title,
        'price': f'￥{price}' if price is not None else None,
        'full_price': f'￥{full_price}' if full_price is not None else None,
        'city': detected_city if detected_city else None
    }
    
    return result
    
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
