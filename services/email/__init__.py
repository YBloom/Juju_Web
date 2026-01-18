"""
Email Service Module - AWS SES SMTP
"""
from .sender import (
    send_email,
    send_verification_code,
    send_welcome_email,
    notify_feedback_received,
)

__all__ = [
    "send_email",
    "send_verification_code",
    "send_welcome_email",
    "notify_feedback_received",
]
