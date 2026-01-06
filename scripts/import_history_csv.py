#!/usr/bin/env python3
"""
历史数据 CSV 导入脚本
用于将 y.saoju.net 导出的演出数据导入 SaojuShow 表

用法:
    # 导入单个文件
    python scripts/import_history_csv.py data/history_data/2026_patch.csv
    
    # 导入多个文件
    python scripts/import_history_csv.py data/history_data/2026_patch.csv data/history_data/2023_2.csv
    
    # 预览模式（不实际写入）
    python scripts/import_history_csv.py --dry-run data/history_data/2026_patch.csv

CSV 格式要求:
    时间,城市,音乐剧,卡司,剧院
    2026-01-01 19:30,上海,阿波罗尼亚,理查德:XXX 奥斯卡:YYY,星空间1号
"""

import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.db.connection import session_scope
from services.hulaquan.tables import SaojuShow


def parse_datetime(dt_str: str) -> datetime:
    """解析日期时间字符串 (支持多种格式)"""
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {dt_str}")


def import_csv(csv_path: str, dry_run: bool = False) -> dict:
    """
    导入单个 CSV 文件到 SaojuShow 表
    
    Returns:
        dict: {"total": 总行数, "inserted": 新增数, "skipped": 跳过数}
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {csv_path}")
    
    stats = {"total": 0, "inserted": 0, "skipped": 0, "errors": 0}
    
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        # 验证列名
        expected_cols = {"时间", "城市", "音乐剧"}
        if not expected_cols.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV 缺少必需列: {expected_cols - set(reader.fieldnames or [])}")
        
        rows_to_insert = []
        
        for row in reader:
            stats["total"] += 1
            
            try:
                dt = parse_datetime(row["时间"])
                musical_name = row["音乐剧"].strip()
                city = row["城市"].strip()
                cast_str = row.get("卡司", "").strip() or None
                theatre = row.get("剧院", "").strip() or None
                
                if not musical_name or not city:
                    stats["errors"] += 1
                    continue
                
                rows_to_insert.append({
                    "date": dt,
                    "musical_name": musical_name,
                    "city": city,
                    "cast_str": cast_str,
                    "theatre": theatre,
                    "source": "csv_patch",
                })
            except Exception as e:
                print(f"  ⚠ 行 {stats['total']} 解析错误: {e}")
                stats["errors"] += 1
    
    if dry_run:
        print(f"  [预览模式] 将导入 {len(rows_to_insert)} 条记录")
        stats["inserted"] = len(rows_to_insert)
        return stats
    
    # 批量写入数据库
    with session_scope() as session:
        for row_data in rows_to_insert:
            # 检查是否已存在 (按主键 date + musical_name)
            existing = session.get(SaojuShow, (row_data["date"], row_data["musical_name"]))
            
            if existing:
                stats["skipped"] += 1
            else:
                show = SaojuShow(**row_data)
                session.add(show)
                stats["inserted"] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="导入历史演出数据 CSV")
    parser.add_argument("files", nargs="+", help="要导入的 CSV 文件路径")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际写入")
    args = parser.parse_args()
    
    print("=" * 50)
    print("历史数据导入工具")
    print("=" * 50)
    
    if args.dry_run:
        print("⚠ 预览模式 - 不会实际写入数据库\n")
    
    total_stats = Counter()
    
    for csv_file in args.files:
        print(f"\n📂 处理文件: {csv_file}")
        try:
            stats = import_csv(csv_file, dry_run=args.dry_run)
            print(f"  ✅ 总行数: {stats['total']}, 新增: {stats['inserted']}, 跳过: {stats['skipped']}, 错误: {stats['errors']}")
            for k, v in stats.items():
                total_stats[k] += v
        except Exception as e:
            print(f"  ❌ 导入失败: {e}")
    
    print("\n" + "=" * 50)
    print("📊 汇总:")
    print(f"   总处理: {total_stats['total']} 条")
    print(f"   新增:   {total_stats['inserted']} 条")
    print(f"   跳过:   {total_stats['skipped']} 条 (已存在)")
    print(f"   错误:   {total_stats['errors']} 条")
    print("=" * 50)


if __name__ == "__main__":
    main()
