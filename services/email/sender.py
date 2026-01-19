"""
邮件发送服务 - 支持 AWS SES (SMTP 方式)
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

log = logging.getLogger(__name__)

# 邮件模板
EMAIL_TEMPLATES = {
    "verification": {
        "subject": "【MusicalBot】邮箱验证码",
        "body": """
您好！

您的验证码是：{code}

此验证码 {expires_minutes} 分钟内有效，请勿泄露给他人。

如果这不是您的操作，请忽略此邮件。

---
MusicalBot 呼啦圈学生票助手
""".strip()
    },
    "reset_password": {
        "subject": "【MusicalBot】密码重置",
        "body": """
您好！

您正在重置密码，验证码是：{code}

此验证码 {expires_minutes} 分钟内有效。

如果这不是您的操作，请立即检查账号安全。

---
MusicalBot 呼啦圈学生票助手
""".strip()
    },
    "welcome": {
        "subject": "【MusicalBot】欢迎注册",
        "body": """
您好！

恭喜您成功注册 MusicalBot 账号！

现在您可以：
✅ 管理演出订阅
✅ 接收学生票上新通知
✅ 查看演出排期

访问：https://yyj.yaobii.com

---
MusicalBot 呼啦圈学生票助手
""".strip()
    }
}


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None
) -> bool:
    """
    发送邮件（使用 AWS SES SMTP）
    
    Returns:
        bool: 是否发送成功
    """
    # Lazy load config
    AWS_SES_SMTP_HOST = os.getenv("AWS_SES_SMTP_HOST", "email-smtp.ap-southeast-1.amazonaws.com")
    AWS_SES_SMTP_PORT = int(os.getenv("AWS_SES_SMTP_PORT", "587"))
    AWS_SES_SMTP_USER = os.getenv("AWS_SES_SMTP_USER")
    AWS_SES_SMTP_PASSWORD = os.getenv("AWS_SES_SMTP_PASSWORD")
    AWS_SES_SENDER = os.getenv("AWS_SES_SENDER", "noreply@yaobii.com")

    if not AWS_SES_SMTP_USER or not AWS_SES_SMTP_PASSWORD:
        log.error("❌ AWS SES 未配置：缺少 AWS_SES_SMTP_USER 或 AWS_SES_SMTP_PASSWORD")
        return False
    
    try:
        # 创建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = AWS_SES_SENDER
        msg["To"] = to_email
        
        # 添加纯文本内容
        part_text = MIMEText(body, "plain", "utf-8")
        msg.attach(part_text)
        
        # 添加 HTML 内容（如果有）
        if html_body:
            part_html = MIMEText(html_body, "html", "utf-8")
            msg.attach(part_html)
        
        # 发送邮件
        with smtplib.SMTP(AWS_SES_SMTP_HOST, AWS_SES_SMTP_PORT) as server:
            server.starttls()  # 启用 TLS
            server.login(AWS_SES_SMTP_USER, AWS_SES_SMTP_PASSWORD)
            server.sendmail(AWS_SES_SENDER, to_email, msg.as_string())
        
        log.info(f"✉️ [邮件] 发送成功: {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        log.error(f"❌ SMTP 认证失败: {e}")
        return False
    except smtplib.SMTPException as e:
        log.error(f"❌ SMTP 发送失败: {e}")
        return False
    except Exception as e:
        log.error(f"❌ 邮件发送异常: {e}")
        return False


async def send_verification_code(email: str, code: str, purpose: str = "verification") -> bool:
    """发送验证码邮件"""
    template = EMAIL_TEMPLATES.get(purpose, EMAIL_TEMPLATES["verification"])
    
    body = template["body"].format(code=code, expires_minutes=10)
    subject = template["subject"]
    
    return await send_email(email, subject, body)


async def send_welcome_email(email: str) -> bool:
    """发送欢迎邮件"""
    template = EMAIL_TEMPLATES["welcome"]
    return await send_email(email, template["subject"], template["body"])


# === 反馈通知（从旧 service.py 迁移） ===

FEEDBACK_NOTIFY_EMAIL = os.getenv("FEEDBACK_NOTIFY_EMAIL", "dev@yaobii.com")


async def notify_feedback_received(
    feedback_type: str,
    content: str,
    contact: str = None
) -> bool:
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
    
    body = f"""
[{type_label}]

{content}

{f'联系方式: {contact}' if contact else ''}

---
MusicalBot 自动通知
管理后台: https://yyj.yaobii.com/admin
    """.strip()
    
    return await send_email(FEEDBACK_NOTIFY_EMAIL, subject, body)
