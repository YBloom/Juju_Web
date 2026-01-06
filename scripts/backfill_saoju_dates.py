#!/usr/bin/env python3
"""
补充历史日期数据脚本
使用 Saoju API 爬取指定日期范围的演出数据

用法:
    # 补充2026年1月1-4日的数据
    python scripts/backfill_saoju_dates.py 2026-01-01 2026-01-04
    
    # 预览模式
    python scripts/backfill_saoju_dates.py --dry-run 2026-01-01 2026-01-04
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.saoju.service import SaojuService
from services.db.connection import session_scope
from services.hulaquan.tables import SaojuShow
from services.utils.timezone import now as timezone_now


async def backfill_date(service: SaojuService, date_str: str, dry_run: bool = False) -> dict:
    """
    爬取指定日期的演出数据并存入数据库
    
    Returns:
        {"total": 总数, "inserted": 新增, "updated": 更新}
    """
    stats = {"total": 0, "inserted": 0, "updated": 0, "skipped": 0}
    
    try:
        data = await service._fetch_json("search_day/", params={"date": date_str})
        if not data or "show_list" not in data:
            print(f"  ⚠ {date_str}: 无数据返回")
            return stats
        
        shows = data["show_list"]
        stats["total"] = len(shows)
        
        if dry_run:
            print(f"  [预览] {date_str}: {len(shows)} 条记录")
            stats["inserted"] = len(shows)
            return stats
        
        with session_scope() as session:
            for item in shows:
                musical_name = item.get("musical")
                time_part = item.get("time")  # HH:MM
                
                if not musical_name or not time_part:
                    continue
                
                try:
                    full_dt = datetime.strptime(f"{date_str} {time_part}", "%Y-%m-%d %H:%M")
                except ValueError:
                    continue
                
                # 构建卡司字符串
                cast_list = item.get("cast", [])
                parts = []
                for c in cast_list:
                    artist = c.get("artist")
                    if not artist:
                        continue
                    role = c.get("role")
                    if role:
                        parts.append(f"{role}:{artist}")
                    else:
                        parts.append(artist)
                cast_str = " / ".join(parts)
                
                city = item.get("city", "")
                theatre = item.get("theatre", "")
                
                # 检查是否已存在
                existing = session.get(SaojuShow, (full_dt, musical_name))
                
                if not existing:
                    show_db = SaojuShow(
                        date=full_dt,
                        city=city,
                        musical_name=musical_name,
                        cast_str=cast_str,
                        theatre=theatre,
                        source="api_backfill",
                        updated_at=timezone_now()
                    )
                    session.add(show_db)
                    stats["inserted"] += 1
                else:
                    # 更新现有记录（如果有变化）
                    if existing.cast_str != cast_str or existing.theatre != theatre:
                        existing.cast_str = cast_str
                        existing.theatre = theatre
                        existing.city = city
                        existing.source = "api_backfill"
                        existing.updated_at = timezone_now()
                        session.add(existing)
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
        
        print(f"  ✅ {date_str}: {stats['total']}条, 新增{stats['inserted']}, 更新{stats['updated']}, 跳过{stats['skipped']}")
        
    except Exception as e:
        print(f"  ❌ {date_str}: 错误 - {e}")
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description="补充历史日期的演出数据")
    parser.add_argument("start_date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("end_date", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入数据库")
    args = parser.parse_args()
    
    try:
        start = datetime.strptime(args.start_date, "%Y-%m-%d")
        end = datetime.strptime(args.end_date, "%Y-%m-%d")
    except ValueError:
        print("❌ 日期格式错误，请使用 YYYY-MM-DD")
        sys.exit(1)
    
    if start > end:
        print("❌ 开始日期不能晚于结束日期")
        sys.exit(1)
    
    # 生成日期列表
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    print("=" * 50)
    print(f"Saoju 历史数据补充工具")
    print("=" * 50)
    print(f"日期范围: {args.start_date} 至 {args.end_date} ({len(dates)}天)")
    
    if args.dry_run:
        print("⚠ 预览模式 - 不会实际写入数据库\n")
    else:
        print("")
    
    # 初始化服务
    service = SaojuService()
    await service._ensure_session()
    
    total_stats = {"total": 0, "inserted": 0, "updated": 0, "skipped": 0}
    
    try:
        for date_str in dates:
            stats = await backfill_date(service, date_str, dry_run=args.dry_run)
            for k, v in stats.items():
                total_stats[k] += v
            # 避免请求过快
            await asyncio.sleep(0.2)
    finally:
        await service.close()
    
    print("\n" + "=" * 50)
    print("📊 汇总:")
    print(f"   总记录: {total_stats['total']} 条")
    print(f"   新增:   {total_stats['inserted']} 条")
    print(f"   更新:   {total_stats['updated']} 条")
    print(f"   跳过:   {total_stats['skipped']} 条 (无变化)")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
