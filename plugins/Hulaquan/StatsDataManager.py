from plugins.Hulaquan import HulaquanDataManager
from plugins.Hulaquan import BaseDataManager
from plugins.Hulaquan.utils import *
import copy


ON_COMMAND_TIMES = "on_command_times"
HLQ_TICKETS_REPO = "hlq_tickets_repo"
USER_ID = 'user_id'
REPORT_ID = 'report_id'  # 报错ID
LATEST_REPO_ID = 'latest_repo_id'
REPORT_ERROR_DETAILS = 'report_error_details'  # 报错用户ID
EVENT_ID_TO_EVENT_TITLE = 'event_id_to_event_title'
LATEST_EVENT_ID = 'latest_event_id'
LATEST_20_REPOS = 'latest_20_repos'

Hlq: HulaquanDataManager = HulaquanDataManager

maxLatestReposCount = 20
maxErrorTimes = 3  # 报错次数超过2次则删除report

class StatsDataManager(BaseDataManager):
    """
    功能：
    进行数据统计
    """

    def on_load(self):
        self.data.setdefault(ON_COMMAND_TIMES, {})
        self.data.setdefault(HLQ_TICKETS_REPO, {})
        self.data.setdefault(EVENT_ID_TO_EVENT_TITLE, {})
        self.data.setdefault(LATEST_REPO_ID, 1000)
        self.data.setdefault(LATEST_EVENT_ID, 100000)
        self.data.setdefault(LATEST_20_REPOS, []) #[(event_id, report_id]
        self.check_events_to_title_dict()

    def on_command(self, command_name):
        self.data[ON_COMMAND_TIMES].setdefault(command_name, 0)
        self.data[ON_COMMAND_TIMES][command_name] += 1
        
    def get_on_command_times(self, command_name):
        return self.data[ON_COMMAND_TIMES][command_name]
    
    def new_id(self, id_key: str):
        self.data[id_key] += 1
        return str(self.data[id_key])
    
    def new_repo(self, title, date, price, seat, content, user_id, category, payable, img=None, event_id=None):
        #用户输入price，content，img，seat
        price = str(price)
        user_id = str(user_id)
        event_id = self.register_event(title, event_id)
        if event_id not in self.data[HLQ_TICKETS_REPO]:
            self.data[HLQ_TICKETS_REPO][event_id] = {}
        report_id = self.new_id(LATEST_REPO_ID)
        self.data[HLQ_TICKETS_REPO][event_id].setdefault(report_id, {})
        self.data[HLQ_TICKETS_REPO][event_id][report_id] = {USER_ID:user_id, 
                                                                "content":content, 
                                                                "price": price,
                                                                "seat":seat,
                                                                "img":img,
                                                                "date":date,
                                                                "category":category,
                                                                "payable":payable,
                                                                "create_time":now_time_str(),
                                                                "event_title": title,
                                                                "event_id": event_id,
                                                                REPORT_ID: report_id,
                                                                REPORT_ERROR_DETAILS: {},
                                                            }
        self.add_in_latest_20_repos(report_id, event_id)
        return report_id
    
    def del_repo(self, report_id, user_id):
        for eid, event in self.data[HLQ_TICKETS_REPO].items():
            if report_id in event:
                if event[report_id][USER_ID] != user_id:
                    return False
                repo = copy.deepcopy(event[report_id])
                del event[report_id]
                return self.generate_repo_report_messages([repo])
        return False
    
    def add_in_latest_20_repos(self, repo_id, event_id):
        tpl = (repo_id, event_id)
        if tpl in self.data[LATEST_20_REPOS]:
            self.data[LATEST_20_REPOS].pop(self.data[LATEST_20_REPOS].index(tpl))
        while len(self.data[LATEST_20_REPOS]) >= maxLatestReposCount:
            self.data[LATEST_20_REPOS].pop(0)
        self.data[LATEST_20_REPOS].append(tpl)
        return tpl
    
    def show_latest_repos(self, count):
        if count > maxLatestReposCount:
            return False
        if count > len(self.data[LATEST_20_REPOS]):
            count = len(self.data[LATEST_20_REPOS])
        events = []
        for i in self.data[LATEST_20_REPOS][::-1][:count]:
            repo_id, event_id = i
            events.append(self.data[HLQ_TICKETS_REPO][event_id][repo_id])
        return self.generate_repo_report_messages(events)

    
    def get_repos(self, event_id, price=None):
        if event_id not in self.data[HLQ_TICKETS_REPO]:
            return {}
        events = self.data[HLQ_TICKETS_REPO][event_id]
        if price:
            return {k: v for k, v in events.items() if v["price"] == price}
        return events
    
    def modify_repo(self, user_id, report_id, date=None, price=None, seat=None, content=None, category=None, payable=None, isOP=False):
        user_id = str(user_id)
        for eid, event in self.data[HLQ_TICKETS_REPO].items():
            if report_id in event:
                if user_id != event[report_id][USER_ID] and not isOP:
                    return False
                if date:
                    event[report_id]["date"] = date
                if category:
                    event[report_id]["category"] = category
                if price:
                    event[report_id]["price"] = str(price)
                if seat:
                    event[report_id]["seat"] = seat
                if payable:
                    event[report_id]["payable"] = str(payable)
                if content:
                    event[report_id]["content"] = content
                repo = event[report_id]
                self.add_in_latest_20_repos(report_id, eid)
                return self.generate_repo_report_messages([repo])
        return False
    
    def get_users_repo(self, user_id: str, is_other=False):
        user_id = str(user_id)
        repos = []
        for eid, event in self.data[HLQ_TICKETS_REPO].items():
            for report_id, report in event.items():
                if report[USER_ID] == user_id:
                    repos.append(report)
        messages = self.generate_repo_report_messages(repos)
        if messages:
            prefix = user_id if is_other else "您"
            messages.insert(0, f"{prefix}共有{len(messages)}条学生票座位记录：\n")
        return messages

    def generate_repo_report_messages(self, events: list):
        messages = []
        for event in events:
            content = event["content"]
            price = event["price"]
            payable = event.get('payable', "")
            category =  event.get('category', "学生票")
            seat = event["seat"]
            date = event["date"]
            title = event["event_title"]
            report_id = event[REPORT_ID]
            create_time = event["create_time"]
            error_details = list(event.get(REPORT_ERROR_DETAILS, {}).values())
            error_msg = "\n".join([f"{i}.{error_details[i]}" for i in range(len(error_details))] if error_details else [])
            img = event.get("img", None)
            report_msg = f"repoID: {report_id}\n剧名：{title}\n【{category}】 ￥{price}（原价￥{payable}）💰 \n座位：{seat}\n演出日期: {date}\n座位描述: {content}\n"
            if error_details:
                report_msg += f"她人汇报repo错误（可能由于时间跨度或各种随机因素导致）: {error_msg}\n"
            messages.append(report_msg)
        return messages

    def get_event_student_seat_repo(self, event_id, price=None):
        events = list(self.get_repos(event_id, price).values())
        messages = self.generate_repo_report_messages(events)
        return messages
    
    def get_repos_list(self):
        
        def get_max_length(lst):
            max_width = 0
            for i in lst:
                width = get_display_width(i)
                if width > max_width:
                    max_width = width
            return max_width
        
        messages = []
        title_list = []
        eid_list = list(self.data[HLQ_TICKETS_REPO].keys())
        for eid in eid_list:
            title = self.get_event_title(eid)
            title_list.append(title)
        title_width = get_max_length(title_list)
        count_width = 4
        messages.append(f"{ljust_for_chinese('剧名', title_width)}{'repo数量'.ljust(count_width)}")
        cnt = {}
        for i in range(len(eid_list)):
            eid = eid_list[i]
            title = title_list[i]
            cnt[title] = len(self.data[HLQ_TICKETS_REPO][eid])
        counts = sorted(cnt.items(), key=lambda x: x[1], reverse=True)
        for title, i in counts:
            messages.append(f"{ljust_for_chinese(title, title_width)}{str(i).ljust(count_width)}")
        return messages

    def report_repo_error(self, report_id, report_user_id: str, error_reason=""):
        report_user_id = str(report_user_id)
        for eid, event in self.data[HLQ_TICKETS_REPO].items():
            if report_id in event:
                event_id = eid
                break
        if report_user_id not in self.data[HLQ_TICKETS_REPO][event_id][report_id][REPORT_ERROR_DETAILS].keys():
            self.data[HLQ_TICKETS_REPO][event_id][report_id][REPORT_ERROR_DETAILS][report_user_id] = []
        self.data[HLQ_TICKETS_REPO][event_id][report_id][REPORT_ERROR_DETAILS][report_user_id].append(error_reason)
        times = self.check_error_times(event_id, report_id)
        if times >= maxErrorTimes:
            return "由于报错次数过多，已删除该report"
        return f"已记录报错，当前报错次数：{times}次"

    def check_error_times(self, event_id, report_id):
        if event_id not in self.data[HLQ_TICKETS_REPO]:
            return -1
        if report_id not in self.data[HLQ_TICKETS_REPO][event_id]:
            return -1
        repo = self.data[HLQ_TICKETS_REPO][event_id][report_id][REPORT_ERROR_DETAILS]
        times = len(repo)
        if times >= maxErrorTimes:
            self.del_repo(event_id, report_id)
        return times
    
    def register_event(self, title, eid=None):
        title = extract_text_in_brackets(title, True)
        if alias := Hlq.alias_search_names(title[1:-1]):
            title = alias[0]
        if eid and eid not in self.data[EVENT_ID_TO_EVENT_TITLE]:
            if eid in self.data[HLQ_TICKETS_REPO]:
                title = list(self.data[HLQ_TICKETS_REPO][eid].values())[0]['event_title']
            self.data[EVENT_ID_TO_EVENT_TITLE][eid] = {'title':title, 'create_time':now_time_str()}  # 修正为调用函数
            return eid
        elif not eid:
            if eid := self.get_event_id(title):
                return eid
            event_id = self.new_id(LATEST_EVENT_ID)
            self.data[EVENT_ID_TO_EVENT_TITLE][event_id] = {'title':title, 'create_time':now_time_str()}  # 修正为调用函数
            return event_id
        else:
            return eid
    
    def get_event_id(self, title):
        for eid, event in self.data[EVENT_ID_TO_EVENT_TITLE].items():
            if title in event['title']:
                return eid
        return 0
    
    def get_event_title(self, eid):
        if eid not in self.data[EVENT_ID_TO_EVENT_TITLE]:
            if len(self.data[HLQ_TICKETS_REPO][eid]) <= 0:
                return False
            title = extract_text_in_brackets(list(self.data[HLQ_TICKETS_REPO][eid].values())[0]["event_title"])
            for report_id in list(self.data[HLQ_TICKETS_REPO][eid].keys()):
                self.data[HLQ_TICKETS_REPO][eid][report_id]["event_title"] = title
            self.data[EVENT_ID_TO_EVENT_TITLE][eid] = {'title':title, 'create_time':now_time_str()}  # 修正为调用函数
            return title
        return self.data[EVENT_ID_TO_EVENT_TITLE][eid]['title']

    def check_events_to_title_dict(self):
        for eid in list(self.data[HLQ_TICKETS_REPO].keys()):
            self.get_event_title(eid)
    
    def del_event(self, event_id):
        if event_id in self.data[EVENT_ID_TO_EVENT_TITLE]:
            del self.data[EVENT_ID_TO_EVENT_TITLE][event_id]
            if event_id in self.data[HLQ_TICKETS_REPO]:
                del self.data[HLQ_TICKETS_REPO][event_id]
            return True
        return False

