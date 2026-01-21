#!/usr/bin/env python3.12
"""
SubscriptionTarget Health & Compatibility Auditor
方案四：订阅目标健康度与兼容性审计工具
"""

import sys
import os
from collections import Counter
from typing import List, Dict, Any

# Ensure we can import from the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select, func, Session, text
from services.db.connection import get_engine
from services.db.models import SubscriptionTarget, Play, SubscriptionTargetKind
from services.hulaquan.tables import HulaquanCast, HulaquanEvent

def print_header(title: str):
    print(f"\n{'='*20} {title} {'='*20}")

def print_bar_chart(data: Dict[str, int], title: str = "分布图"):
    if not data:
        print(f"{title}: 无数据")
        return
    
    # 过滤掉非整数值
    numeric_data = {k: v for k, v in data.items() if isinstance(v, int)}
    if not numeric_data:
        print(f"{title}: 无数值记录")
        return

    max_val = max(numeric_data.values())
    max_label_len = max(len(str(k)) for k in numeric_data.keys())
    chart_width = 40
    
    print(f"\n{title}:")
    for key, val in sorted(numeric_data.items(), key=lambda x: x[1], reverse=True):
        bar_len = int((val / max_val) * chart_width) if max_val > 0 else 0
        bar = "█" * bar_len
        print(f"{str(key).ljust(max_label_len)} | {bar} {val}")

def audit_kinds(session: Session):
    print_header("1. 枚举规范化检测")
    
    # 统计 kind 分布
    statement = select(SubscriptionTarget.kind, func.count(SubscriptionTarget.id)).group_by(SubscriptionTarget.kind)
    results = session.exec(statement).all()
    
    # 处理枚举成员名，使其在图表中更易读
    kind_counts = {}
    for k, c in results:
        # SQLModel 枚举字段返回时已经是 Enum 成员
        label = k.name if hasattr(k, 'name') else str(k)
        kind_counts[label] = c

    print_bar_chart(kind_counts, "SubscriptionTarget.kind 分布")
    
    # 检测异常值 (预期全大写，匹配 Enum 成员名)
    valid_kinds = {k.name for k in SubscriptionTargetKind}
    anomalies = []
    
    # 直接查询数据库原始字符串值
    raw_results = session.execute(text("SELECT DISTINCT kind FROM subscriptiontarget")).all()
    for row in raw_results:
        kind_str = str(row[0]) if row[0] else ""
        if kind_str not in valid_kinds:
            anomalies.append(kind_str)
            
    if anomalies:
        print(f"\n[!] 发现非标 kind 字符串: {anomalies}")
        for a in anomalies:
            count = session.execute(text(f"SELECT COUNT(*) FROM subscriptiontarget WHERE kind = '{a}'")).scalar()
            print(f"  - '{a}': {count} 条记录")
    else:
        print("\n[✓] 所有 kind 字段均符合枚举规范 (大写成员名格式)。")

import re

def normalize_target_name(name: str) -> str:
    if not name: return ""
    # 去除常见的描述性前缀后缀
    # e.g. 音乐剧《连璧》 -> 连璧
    # e.g. 惊悚推理音乐剧《奥尔菲斯》 -> 奥尔菲斯
    name = re.sub(r"^(?:音乐剧|歌剧|话剧|惊悚|推理|悬疑|沉浸式|环境式|原创|经典|大型|百老汇|中文版)+", "", name)
    name = re.sub(r"(?:音乐剧|中文版|巡演|演出)+$", "", name)
    # 去除书名号
    name = re.sub(r"[《》]", "", name)
    return name.strip().lower()

def audit_fuzzy_matching(session: Session):
    print_header("2. 模糊匹配命中率分析")
    
    # 1. 检查 Play 订阅的匹配情况
    play_targets = session.exec(select(SubscriptionTarget).where(SubscriptionTarget.kind == SubscriptionTargetKind.PLAY)).all()
    print(f"检测剧目订阅: 共 {len(play_targets)} 条")
    
    play_miss_count = 0
    play_soft_match_count = 0
    play_miss_examples = []
    
    # 获取所有 Play 标题及别名用于比对
    all_plays = {p.name.strip().lower(): p.name for p in session.exec(select(Play)).all()}
    from services.db.models import PlayAlias
    all_play_aliases = {a.alias.strip().lower(): a.play_id for a in session.exec(select(PlayAlias)).all()}
    
    # 获取 HulaquanEvent 数据作为兜底
    from services.hulaquan.tables import HulaquanEvent
    # 用 title 做 key
    all_hulaquan_events = {e.title.strip().lower(): e.title for e in session.exec(select(HulaquanEvent)).all()}

    # 规范化后的 Play 表
    norm_plays = {normalize_target_name(p.name): p.name for p in session.exec(select(Play)).all()}
    all_plays_norm = {p.name_norm.strip().lower(): p.name for p in session.exec(select(Play)).all()}
    norm_aliases = {normalize_target_name(a.alias): a.play_id for a in session.exec(select(PlayAlias)).all()}
    
    # 规范化后的 HulaquanEvent
    norm_hulaquan = {normalize_target_name(e.title): e.title for e in session.exec(select(HulaquanEvent)).all()}

    for target in play_targets:
        if not target.name:
            continue
            
        clean_name = target.name.strip().lower()
        
        # 1. 检查 Play 表 (及别名)
        if clean_name in all_plays or clean_name in all_play_aliases or clean_name in all_plays_norm:
            continue
            
        # 2. 尝试 Play 表“软匹配”
        soft_name = normalize_target_name(target.name)
        if soft_name in norm_plays or soft_name in norm_aliases:
            play_soft_match_count += 1
            continue
            
        # 3. 兜底检查 HulaquanEvent (原始数据)
        if clean_name in all_hulaquan_events:
            # 精确匹配到 HulaquanEvent
            play_soft_match_count += 1 # 算作通过，但也可以单独计数
            continue
            
        if soft_name in norm_hulaquan:
            # 软匹配到 HulaquanEvent
            play_soft_match_count += 1
            continue

        play_miss_count += 1
        if len(play_miss_examples) < 5:
            play_miss_examples.append(target.name)
                
    if play_soft_match_count > 0:
        print(f"[i] 软匹配/兜底成功：{play_soft_match_count} 条剧目通过前缀匹配或 HulaquanEvent 兜底成功。")
    
    if play_miss_count > 0:
        print(f"[!] 最终失配：{play_miss_count} 条剧目订阅系统库全无记录 (Play/Hulaquan)。")
        print(f"    示例: {play_miss_examples}")
    else:
        print("[✓] 剧目订阅匹配良好 (Play库或Hulaquan原始库)。")

    # 2. 检查 Actor (Cast) 订阅的匹配情况
    actor_targets = session.exec(select(SubscriptionTarget).where(SubscriptionTargetKind.ACTOR == SubscriptionTarget.kind)).all()
    print(f"\n检测卡司订阅: 共 {len(actor_targets)} 条")
    
    actor_miss_count = 0
    actor_miss_examples = []
    
    all_casts = {c.name.strip().lower(): c.name for c in session.exec(select(HulaquanCast)).all()}
    
    for target in actor_targets:
        if not target.name:
            continue
            
        clean_name = target.name.strip().lower()
        if clean_name not in all_casts:
            actor_miss_count += 1
            if len(actor_miss_examples) < 5:
                actor_miss_examples.append(target.name)
                
    if actor_miss_count > 0:
        print(f"[!] 卡司匹配：{actor_miss_count} 条订阅在 HulaquanCast 表中无精确匹配。")
        print(f"    示例: {actor_miss_examples}")
    else:
        print("[✓] 所有卡司订阅均能在 HulaquanCast 表中找到匹配。")

def main():
    engine = get_engine()
    with Session(engine) as session:
        audit_kinds(session)
        audit_fuzzy_matching(session)
    
    print_header("审计结束")

if __name__ == "__main__":
    main()
