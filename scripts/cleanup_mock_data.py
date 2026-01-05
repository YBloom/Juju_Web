import os
import sys

# 设置路径以导入服务
sys.path.append(os.getcwd())

from services.hulaquan.tables import Feedback, HulaquanEvent, HulaquanTicket, TicketCastAssociation
from services.db.connection import session_scope
from sqlmodel import select, delete

def cleanup():
    print("开始清理 Mock 数据...")
    with session_scope() as session:
        # 1. 删除 TicketCastAssociation (如果有)
        stmt1 = delete(TicketCastAssociation).where(TicketCastAssociation.ticket_id == 'test_t1')
        session.exec(stmt1)
        
        # 2. 删除 HulaquanTicket
        stmt2 = delete(HulaquanTicket).where(HulaquanTicket.id == 'test_t1')
        session.exec(stmt2)
        
        # 3. 删除 HulaquanEvent
        stmt3 = delete(HulaquanEvent).where(HulaquanEvent.id == 'test_e1')
        session.exec(stmt3)
        
        # 4. 删除测试 Feedback
        stmt4 = delete(Feedback).where(Feedback.content == 'Concurrency Test')
        session.exec(stmt4)
        
        session.commit()
        print("清理完成！已删除 ID 为 test_t1 的票务、test_e1 的剧目以及测试反馈。")

if __name__ == "__main__":
    cleanup()
