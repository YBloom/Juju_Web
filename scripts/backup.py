#!/usr/bin/env python3
"""
MusicalBot 数据备份脚本
支持 SQLite WAL 模式的热备份、文件压缩和自动清理
"""

import os
import sqlite3
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
import zipfile

# ======================== 配置区 ========================
# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 备份目标
DB_PATH = PROJECT_ROOT / "data" / "musicalbot.db"
KEYS_DIR = PROJECT_ROOT / "keys"
ENV_FILE = PROJECT_ROOT / ".env"

# 备份输出
BACKUP_DIR = PROJECT_ROOT / "backups"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "backups.log"

# 保留策略（天数）
RETENTION_DAYS = 7

# ========================================================

# 配置日志
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def backup_sqlite_db(source_db: Path, dest_db: Path) -> None:
    """
    使用 sqlite3.backup() API 进行热备份
    兼容 WAL 模式，即使数据库正在使用也能安全备份
    """
    logger.info(f"正在备份数据库: {source_db.name}")
    
    if not source_db.exists():
        logger.warning(f"数据库文件不存在: {source_db}")
        return
    
    # 确保目标目录存在
    dest_db.parent.mkdir(parents=True, exist_ok=True)
    
    # 使用 Python sqlite3 的 backup API（支持 WAL）
    src_conn = sqlite3.connect(str(source_db))
    dst_conn = sqlite3.connect(str(dest_db))
    
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
        logger.info(f"✓ 数据库备份完成: {source_db.name}")
    except Exception as e:
        logger.error(f"✗ 数据库备份失败: {e}")
        raise
    finally:
        src_conn.close()
        dst_conn.close()


def copy_directory(src: Path, dst: Path) -> None:
    """递归复制目录"""
    if not src.exists():
        logger.warning(f"目录不存在，跳过: {src}")
        return
    
    logger.info(f"正在复制目录: {src.name}")
    shutil.copytree(src, dst, dirs_exist_ok=True)
    logger.info(f"✓ 目录复制完成: {src.name}")


def copy_file(src: Path, dst: Path) -> None:
    """复制单个文件"""
    if not src.exists():
        logger.warning(f"文件不存在，跳过: {src}")
        return
    
    logger.info(f"正在复制文件: {src.name}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.info(f"✓ 文件复制完成: {src.name}")


def create_backup_archive() -> Path:
    """创建备份压缩包"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = BACKUP_DIR / f"temp_{timestamp}"
    archive_name = BACKUP_DIR / f"backup_{timestamp}.zip"
    
    try:
        # 创建临时备份目录
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 备份数据库（热备份）
        backup_sqlite_db(DB_PATH, temp_dir / "musicalbot.db")
        
        # 2. 备份密钥目录
        if KEYS_DIR.exists():
            copy_directory(KEYS_DIR, temp_dir / "keys")
        
        # 3. 备份 .env 配置
        if ENV_FILE.exists():
            copy_file(ENV_FILE, temp_dir / ".env")
        
        # 4. 压缩为 zip
        logger.info(f"正在创建压缩包: {archive_name.name}")
        with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(temp_dir)
                    zipf.write(file_path, arcname)
        
        logger.info(f"✓ 备份压缩包已创建: {archive_name}")
        return archive_name
        
    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.info("临时文件已清理")


def cleanup_old_backups() -> None:
    """删除超过保留期限的旧备份"""
    if not BACKUP_DIR.exists():
        return
    
    cutoff_time = datetime.now() - timedelta(days=RETENTION_DAYS)
    logger.info(f"正在清理 {RETENTION_DAYS} 天前的旧备份...")
    
    deleted_count = 0
    for backup_file in BACKUP_DIR.glob("backup_*.zip"):
        # 从文件名提取时间戳
        try:
            # 文件名格式: backup_20240120_120000.zip
            timestamp_str = backup_file.stem.replace("backup_", "")
            file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            if file_time < cutoff_time:
                backup_file.unlink()
                deleted_count += 1
                logger.info(f"✓ 已删除旧备份: {backup_file.name}")
        except Exception as e:
            logger.warning(f"无法解析备份文件时间: {backup_file.name} - {e}")
    
    if deleted_count > 0:
        logger.info(f"共清理 {deleted_count} 个旧备份")
    else:
        logger.info("没有需要清理的旧备份")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("MusicalBot 数据备份开始")
    logger.info("=" * 60)
    
    try:
        # 确保备份目录存在
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # 创建备份
        archive_path = create_backup_archive()
        
        # 清理旧备份
        cleanup_old_backups()
        
        # 显示备份信息
        archive_size = archive_path.stat().st_size / (1024 * 1024)  # MB
        logger.info("=" * 60)
        logger.info(f"✓ 备份成功完成")
        logger.info(f"备份文件: {archive_path.name}")
        logger.info(f"文件大小: {archive_size:.2f} MB")
        logger.info(f"保存位置: {archive_path}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"✗ 备份失败: {e}")
        logger.error("=" * 60)
        raise


if __name__ == "__main__":
    main()
