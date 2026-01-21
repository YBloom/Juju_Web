#!/usr/bin/env python3.12
"""
用户身份与鉴权映射一致性审计工具 (Identity & Auth Mapping Audit)
诊断目标：确保 6 位数字 UserID 改革后，数据层关联完整且安全。
"""

import sys
import os
import asyncio
import threading
import logging
from typing import List, Set
from concurrent.futures import ThreadPoolExecutor

# 将项目根目录添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.db.connection import session_scope, get_engine
from services.db.models.user import User
from services.db.models.subscription import Subscription
from services.db.models.user_auth_method import UserAuthMethod
from sqlmodel import select, func

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def audit_orphan_records():
    """审计点 1: 孤儿记录检测"""
    print("\n=== [审计点 1: 孤儿记录检测] ===")
    with session_scope() as session:
        # 1.1 Subscription 中的孤儿 (user_id 不在 User 表中)
        sub_user_ids = session.exec(select(Subscription.user_id)).all()
        existing_user_ids = set(session.exec(select(User.user_id)).all())
        
        orphans = [uid for uid in sub_user_ids if uid not in existing_user_ids]
        legacy_ids = [uid for uid in orphans if len(uid) > 6]
        
        print(f"检查 Subscription 表...")
        print(f"  - 总订阅数: {len(sub_user_ids)}")
        print(f"  - 孤儿记录数 (UserID 缺失): {len(orphans)}")
        if orphans:
            print(f"    [!] 发现孤儿 ID 示例: {orphans[:5]}")
        
        print(f"  - 遗留旧 ID 数 (长度 > 6): {len(legacy_ids)}")
        if legacy_ids:
            print(f"    [!] 遗留 ID 示例: {legacy_ids[:5]}")

        # 1.2 UserAuthMethod 中的孤儿
        auth_user_ids = session.exec(select(UserAuthMethod.user_id)).all()
        auth_orphans = [uid for uid in auth_user_ids if uid not in existing_user_ids]
        
        print(f"\n检查 UserAuthMethod 表...")
        print(f"  - 总认证记录数: {len(auth_user_ids)}")
        print(f"  - 孤儿认证数 (UserID 缺失): {len(auth_orphans)}")
        if auth_orphans:
            print(f"    [!] 发现孤儿 Auth ID 示例: {auth_orphans[:5]}")

async def audit_auth_coverage():
    """审计点 2: 多路登录覆盖率"""
    print("\n=== [审计点 2: 多路登录覆盖率] ===")
    with session_scope() as session:
        users = session.exec(select(User)).all()
        total_users = len(users)
        
        coverage = {
            "pure_qq": 0,
            "pure_email": 0,
            "both": 0,
            "none": 0
        }
        
        for user in users:
            auths = session.exec(select(UserAuthMethod).where(UserAuthMethod.user_id == user.user_id)).all()
            providers = {auth.provider for auth in auths}
            
            has_qq = "qq" in providers
            has_email = "email" in providers
            
            if has_qq and has_email:
                coverage["both"] += 1
            elif has_qq:
                coverage["pure_qq"] += 1
            elif has_email:
                coverage["pure_email"] += 1
            else:
                coverage["none"] += 1
        
        print(f"总用户数: {total_users}")
        print(f"  - 纯 QQ 用户: {coverage['pure_qq']} ({coverage['pure_qq']/total_users*100:.1f}%)")
        print(f"  - 纯 Email 用户: {coverage['pure_email']} ({coverage['pure_email']/total_users*100:.1f}%)")
        print(f"  - 双重绑定用户: {coverage['both']} ({coverage['both']/total_users*100:.1f}%)")
        print(f"  - 无认证记录用户 (影子用户): {coverage['none']} ({coverage['none']/total_users*100:.1f}%)")

def test_id_generation_safe():
    """审计点 3: ID 步进安全性检查 (并发模拟)"""
    print("\n=== [审计点 3: ID 步进快照安全性] ===")
    print("正在模拟 10 线程并发生成 50 个 ID...")
    
    generated_ids = []
    lock = threading.Lock()

    def worker():
        # 注意: User.generate_next_id 内部会开启 session 事务
        # 这里测试其跨事务/并发的锁机制
        for _ in range(5):
            uid = User.generate_next_id()
            with lock:
                generated_ids.append(uid)

    threads = []
    for _ in range(10):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    unique_ids = set(generated_ids)
    print(f"生成总数: {len(generated_ids)}")
    print(f"唯一数: {len(unique_ids)}")
    
    if len(generated_ids) != len(unique_ids):
        print("[CRITICAL] 发现重复发号风险！")
        # 找出重复的 ID
        seen = set()
        dupes = [x for x in generated_ids if x in seen or seen.add(x)]
        print(f"重复 ID 示例: {dupes[:5]}")
    else:
        print("[SUCCESS] 并发 ID 生成通过安全性校验。")

async def main():
    print("MusicalBot 身份与鉴权一致性审计启动...")
    try:
        await audit_orphan_records()
        await audit_auth_coverage()
        # 并发测试由于涉及多线程和多事务，直接同步运行
        test_id_generation_safe()
    except Exception as e:
        logger.error(f"审计过程中发生错误: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
