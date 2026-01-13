"""
邮件服务模块
用于发送系统通知邮件（如用户反馈通知）
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

# 邮件配置 - 从环境变量读取
import os

SMTP_CONFIG = {
    "host": os.getenv("SMTP_HOST", "smtp-relay.brevo.com"),
    "port": int(os.getenv("SMTP_PORT", "587")),
    "username": os.getenv("SMTP_USERNAME", ""),
    "password": os.getenv("SMTP_PASSWORD", ""),
    "from_email": os.getenv("SMTP_FROM_EMAIL", "noreply@yaobii.com"),
    "from_name": os.getenv("SMTP_FROM_NAME", "MusicalBot")
}

# 收件人配置
FEEDBACK_NOTIFY_EMAIL = "dev@yaobii.com"


def load_smtp_config():
    """从环境变量加载 SMTP 配置"""
    import os
    global SMTP_CONFIG
    
    SMTP_CONFIG["host"] = os.getenv("SMTP_HOST", SMTP_CONFIG["host"])
    SMTP_CONFIG["port"] = int(os.getenv("SMTP_PORT", SMTP_CONFIG["port"]))
    SMTP_CONFIG["username"] = os.getenv("SMTP_USERNAME", SMTP_CONFIG["username"])
    SMTP_CONFIG["password"] = os.getenv("SMTP_PASSWORD", SMTP_CONFIG["password"])
    SMTP_CONFIG["from_email"] = os.getenv("SMTP_FROM_EMAIL", SMTP_CONFIG["from_email"])
    SMTP_CONFIG["from_name"] = os.getenv("SMTP_FROM_NAME", SMTP_CONFIG["from_name"])


def send_email_sync(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None
) -> bool:
    """
    同步发送邮件
    
    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        body_html: HTML 格式邮件内容
        body_text: 纯文本格式邮件内容（可选，用于不支持 HTML 的客户端）
    
    Returns:
        发送是否成功
    """
    load_smtp_config()
    
    if not SMTP_CONFIG["username"] or not SMTP_CONFIG["password"]:
        logger.warning("⚠️ SMTP 未配置，跳过邮件发送")
        return False
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_CONFIG['from_name']} <{SMTP_CONFIG['from_email']}>"
        msg["To"] = to_email
        
        # 纯文本版本
        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        
        # HTML 版本
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        
        # 连接 SMTP 服务器
        with smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"]) as server:
            server.starttls()
            server.login(SMTP_CONFIG["username"], SMTP_CONFIG["password"])
            server.sendmail(SMTP_CONFIG["from_email"], to_email, msg.as_string())
        
        logger.info(f"✉️ 邮件发送成功: {subject} -> {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 邮件发送失败: {e}")
        return False


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None
) -> bool:
    """异步发送邮件（在线程池中执行同步邮件发送）"""
    return await asyncio.to_thread(send_email_sync, to_email, subject, body_html, body_text)


async def notify_feedback_received(
    feedback_type: str,
    content: str,
    contact: Optional[str] = None
):
    """
    当收到新反馈时发送通知邮件
    
    Args:
        feedback_type: 反馈类型 (bug, suggestion, wish)
        content: 反馈内容
        contact: 联系方式/昵称
    """
    type_labels = {
        "bug": "🐞 Bug 反馈",
        "suggestion": "💡 优化建议", 
        "wish": "✨ 功能许愿"
    }
    type_label = type_labels.get(feedback_type, "📝 用户反馈")
    
    subject = f"[MusicalBot] 新{type_label}"
    
    # HTML 邮件内容
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 20px; }}
            .type-badge {{ display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 14px; font-weight: 600; }}
            .type-bug {{ background: #ffebee; color: #c62828; }}
            .type-suggestion {{ background: #e8f5e9; color: #2e7d32; }}
            .type-wish {{ background: #e3f2fd; color: #1565c0; }}
            .content {{ background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; line-height: 1.6; }}
            .footer {{ color: #999; font-size: 12px; margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; }}
            .contact {{ color: #666; font-size: 14px; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <span class="type-badge type-{feedback_type}">{type_label}</span>
            </div>
            <div class="content">
                {content.replace(chr(10), '<br>')}
            </div>
            {f'<div class="contact">👤 联系方式: {contact}</div>' if contact else ''}
            <div class="footer">
                此邮件由 MusicalBot 自动发送<br>
                <a href="https://musical.yaobii.com/admin">前往后台管理</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 纯文本版本
    body_text = f"""
[{type_label}]

{content}

{f'联系方式: {contact}' if contact else ''}

---
MusicalBot 自动通知
管理后台: https://musical.yaobii.com/admin
    """.strip()
    
    await send_email(FEEDBACK_NOTIFY_EMAIL, subject, body_html, body_text)
