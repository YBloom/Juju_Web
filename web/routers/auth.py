"""
认证路由 - 邮箱登录/注册 + QQ Magic Link
"""
from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from services.db.models import User, UserSession, EmailVerification, UserAuthMethod
from services.db.connection import session_scope
from services.email import send_verification_code, send_welcome_email
from typing import Optional
from sqlmodel import select
import jwt
import logging
import os
import re
import hashlib
import secrets
from datetime import datetime
from services.utils.timezone import now as get_now, make_aware


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Config
JWT_SECRET = os.getenv("JWT_SECRET", "musicalbot-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
SESSION_COOKIE_NAME = "mb_session"
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://127.0.0.1:8000")


def hash_password(password: str) -> str:
    """密码哈希（使用 SHA256 + salt）"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        salt, stored_hash = hashed.split(":")
        return hashlib.sha256((password + salt).encode()).hexdigest() == stored_hash
    except:
        return False






def set_session_cookie(response: Response, session_id: str, request: Request = None):
    """设置 Session Cookie"""
    # Auto-detect secure flag based on request scheme if available
    is_secure = False
    if request:
        is_secure = request.url.scheme == "https"
    else:
        # Fallback to config
        is_secure = WEB_BASE_URL.startswith("https")

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=30 * 24 * 60 * 60,  # 30 天
        httponly=True,
        samesite="lax",
        secure=is_secure
    )


# === Request Models ===

class EmailSendCodeRequest(BaseModel):
    email: EmailStr
    purpose: str = "register"  # register, login, reset_password


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: str
    password: Optional[str] = None  # 仅注册时需要


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


# === IP Rate Limiting (In-Memory) ===
from collections import defaultdict
import time

# IP -> List[timestamp]
# 简单防刷: 1分钟内限制5次请求
IP_RATE_LIMITS = defaultdict(list)

def check_ip_limit(ip: str) -> bool:
    now = time.time()
    # 清理过期记录
    IP_RATE_LIMITS[ip] = [t for t in IP_RATE_LIMITS[ip] if now - t < 60]
    # 允许5次
    return len(IP_RATE_LIMITS[ip]) < 5

def add_ip_record(ip: str):
    IP_RATE_LIMITS[ip].append(time.time())


# === Endpoints ===

@router.post("/email/send-code")
async def send_email_code(req: EmailSendCodeRequest, request: Request):
    """发送邮箱验证码"""
    email = req.email.lower().strip()
    purpose = req.purpose
    
    # 1. IP 限流检查
    client_ip = request.client.host if request.client else "unknown"
    if not check_ip_limit(client_ip):
         return JSONResponse(
            status_code=429,
            content={"error": "请求过于频繁，请稍后重试"}
        )
    
    # 检查用户是否已存在（根据 purpose）
    with session_scope() as db:
        stmt = select(User).where(User.email == email)
        existing_user = db.exec(stmt).first()
        
        if purpose == "register" and existing_user:
            return JSONResponse(
                status_code=400,
                content={"error": "此邮箱已注册，请直接登录", "hint": "login"}
            )
        
        if purpose in ["login", "reset_password"] and not existing_user:
            return JSONResponse(
                status_code=400,
                content={"error": "此邮箱未注册", "hint": "register"}
            )
        
        # 检查发送频率（1分钟内只能发一次）
        stmt = select(EmailVerification).where(
            EmailVerification.email == email,
            EmailVerification.purpose == purpose,
            EmailVerification.used == False
        ).order_by(EmailVerification.created_at.desc())
        
        recent = db.exec(stmt).first()
        if recent:
            now_time = get_now()
            created_at = make_aware(recent.created_at)
            
            if (now_time - created_at).total_seconds() < 60:
                return JSONResponse(
                    status_code=429,
                    content={"error": "发送过于频繁，请稍后再试", "wait_seconds": 60}
                )
        
        # 创建验证码
        verification = EmailVerification.create(email, purpose)
        db.add(verification)
        code = verification.code
    
    # 发送邮件
    success = await send_verification_code(email, code, purpose)
    
    if success:
        # 记录 IP 限制
        add_ip_record(client_ip)
        return {"status": "ok", "message": "验证码已发送到您的邮箱"}
    else:
        # 发送失败，删除数据库记录，避免占用频次
        try:
            with session_scope() as db:
                stmt = select(EmailVerification).where(
                    EmailVerification.email == email,
                    EmailVerification.code == code,
                    EmailVerification.purpose == purpose
                )
                v = db.exec(stmt).first()
                if v:
                    db.delete(v)
        except Exception as e:
            logger.error(f"Failed to rollback verification: {e}")

        return JSONResponse(
            status_code=500,
            content={"error": "邮件发送失败，请稍后重试"}
        )

@router.post("/email/send-code")
async def send_email_code(req: EmailSendCodeRequest, request: Request):
    """发送邮箱验证码"""
    email = req.email.lower().strip()
    purpose = req.purpose
    
    # 1. IP 限流检查
    client_ip = request.client.host if request.client else "unknown"
    if not check_ip_limit(client_ip):
         return JSONResponse(
            status_code=429,
            content={"error": "请求过于频繁，请稍后重试"}
        )
    
    # 检查用户是否已存在（根据 purpose）
    with session_scope() as db:
        stmt = select(User).where(User.email == email)
        existing_user = db.exec(stmt).first()
        
        if purpose == "register" and existing_user:
            return JSONResponse(
                status_code=400,
                content={"error": "此邮箱已注册，请直接登录", "hint": "login"}
            )
        
        if purpose in ["login", "reset_password"] and not existing_user:
            return JSONResponse(
                status_code=400,
                content={"error": "此邮箱未注册", "hint": "register"}
            )
        
        # 检查发送频率（1分钟内只能发一次）
        stmt = select(EmailVerification).where(
            EmailVerification.email == email,
            EmailVerification.purpose == purpose,
            EmailVerification.used == False
        ).order_by(EmailVerification.created_at.desc())
        
        recent = db.exec(stmt).first()
        if recent:
            now_time = get_now()
            created_at = make_aware(recent.created_at)
            
            if (now_time - created_at).total_seconds() < 60:
                return JSONResponse(
                    status_code=429,
                    content={"error": "发送过于频繁，请稍后再试", "wait_seconds": 60}
                )
        
        # 创建验证码
        verification = EmailVerification.create(email, purpose)
        db.add(verification)
        code = verification.code
    
    # 发送邮件
    success = await send_verification_code(email, code, purpose)
    
    if success:
        # 记录 IP 限制
        add_ip_record(client_ip)
        return {"status": "ok", "message": "验证码已发送到您的邮箱"}
    else:
        # 发送失败，删除数据库记录，避免占用频次
        try:
            with session_scope() as db:
                stmt = select(EmailVerification).where(
                    EmailVerification.email == email,
                    EmailVerification.code == code,
                    EmailVerification.purpose == purpose
                )
                v = db.exec(stmt).first()
                if v:
                    db.delete(v)
        except Exception as e:
            logger.error(f"Failed to rollback verification: {e}")

        return JSONResponse(
            status_code=500,
            content={"error": "邮件发送失败，请稍后重试"}
        )


@router.post("/email/register")
async def email_register(req: EmailVerifyRequest, request: Request, response: Response):
    """邮箱注册 - 生成6位数字ID"""
    email = req.email.lower().strip()
    code = req.code
    password = req.password
    
    if not password or len(password) < 6:
        return JSONResponse(status_code=400, content={"error": "密码至少6位"})
    
    session_id = None
    user_id_val = None
    
    with session_scope() as db:
        # 验证验证码
        stmt = select(EmailVerification).where(
            EmailVerification.email == email,
            EmailVerification.purpose == "register",
            EmailVerification.used == False
        ).order_by(EmailVerification.created_at.desc())
        
        verification = db.exec(stmt).first()
        if not verification or not verification.is_valid(code):
            return JSONResponse(status_code=400, content={"error": "验证码无效或已过期"})
        
        # 检查邮箱是否已注册
        stmt = select(UserAuthMethod).where(
            UserAuthMethod.provider == "email",
            UserAuthMethod.provider_user_id == email
        )
        if db.exec(stmt).first():
            return JSONResponse(status_code=400, content={"error": "此邮箱已注册"})
        
        # 生成数字ID
        user_id = User.generate_next_id()
        
        # 创建用户
        user = User(
            user_id=user_id,
            email=email,
            nickname=email.split("@")[0]
        )
        db.add(user)
        
        # 创建认证方式 (密码存储在extra_data中)
        auth_method = UserAuthMethod(
            user_id=user_id,
            provider="email",
            provider_user_id=email,
            is_primary=True,
            extra_data={"password_hash": hash_password(password)}
        )
        db.add(auth_method)
        
        # 标记验证码已使用
        verification.used = True
        db.add(verification)
        
        # 创建 Session
        session = UserSession.create(
            user_id=user_id,
            provider="email",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(session)
        
        # Extract ID while in session to prevent DetachedInstanceError
        session_id = session.session_id
        user_id_val = user.user_id
    
    # 设置 Cookie
    resp = JSONResponse(content={
        "status": "ok",
        "message": "注册成功",
        "user": {"user_id": user_id_val, "email": email}
    })
    
    if session_id:
        set_session_cookie(resp, session_id)
    
    logger.info(f"✨ [注册] 新用户注册: {email} -> user_id={user_id_val}")
    return resp


@router.post("/email/login")
async def email_login(req: EmailLoginRequest, request: Request, response: Response):
    """邮箱密码登录 - 通过UserAuthMethod验证"""
    email = req.email.lower().strip()
    password = req.password
    
    session_id = None
    user_id_val = None
    
    with session_scope() as db:
        # 查询认证方式
        stmt = select(UserAuthMethod).where(
            UserAuthMethod.provider == "email",
            UserAuthMethod.provider_user_id == email
        )
        auth_method = db.exec(stmt).first()
        
        if not auth_method:
            return JSONResponse(status_code=400, content={"error": "邮箱未注册"})
        
        # 验证密码
        password_hash = auth_method.extra_data.get("password_hash") if auth_method.extra_data else None
        if not password_hash or not verify_password(password, password_hash):
            return JSONResponse(status_code=400, content={"error": "密码错误"})
        
        # 创建 Session
        session = UserSession.create(
            user_id=auth_method.user_id,
            provider="email",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(session)

        # Extract ID while in session to prevent DetachedInstanceError
        session_id = session.session_id
        user_id_val = auth_method.user_id
    
    resp = JSONResponse(content={
        "status": "ok",
        "message": "登录成功",
        "user": {"user_id": user_id_val, "email": email}
    })
    
    if session_id:
        set_session_cookie(resp, session_id)
    
    logger.info(f"🔐 [登录] 用户登录: {email}")
    return resp


@router.post("/email/reset-password")
async def reset_password(req: PasswordResetRequest):
    """重置密码 - 更新UserAuthMethod的extra_data"""
    email = req.email.lower().strip()
    code = req.code
    new_password = req.new_password
    
    if len(new_password) < 6:
        return JSONResponse(status_code=400, content={"error": "密码至少6位"})
    
    with session_scope() as db:
        # 验证验证码
        stmt = select(EmailVerification).where(
            EmailVerification.email == email,
            EmailVerification.purpose == "reset_password",
            EmailVerification.used == False
        ).order_by(EmailVerification.created_at.desc())
        
        verification = db.exec(stmt).first()
        if not verification or not verification.is_valid(code):
            return JSONResponse(status_code=400, content={"error": "验证码无效或已过期"})
        
        # 查找认证方式
        stmt = select(UserAuthMethod).where(
            UserAuthMethod.provider == "email",
            UserAuthMethod.provider_user_id == email
        )
        auth_method = db.exec(stmt).first()
        if not auth_method:
            return JSONResponse(status_code=400, content={"error": "用户不存在"})
        
        # 更新密码
        if not auth_method.extra_data:
            auth_method.extra_data = {}
        auth_method.extra_data["password_hash"] = hash_password(new_password)
        db.add(auth_method)
        
        # 标记验证码已使用
        verification.used = True
        db.add(verification)
    
    logger.info(f"🔑 [密码重置] 用户重置密码: {email}")
    return {"status": "ok", "message": "密码重置成功，请重新登录"}


# === QQ Magic Link ===

@router.get("/magic-link")
async def login_with_magic_link(token: str, request: Request, response: Response, redirect: Optional[str] = None):
    """QQ Magic Link 登录 - 通过UserAuthMethod查询或创建用户"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        qq_id = payload.get("qq_id")
        nickname = payload.get("nickname", "User")
        
        if not qq_id:
            raise HTTPException(status_code=400, detail="Invalid Token Payload")
        
        logger.info(f"🔐 [Auth] Magic Link Login: QQ {qq_id}")
        
        with session_scope() as db:
            # 查询是否已有此QQ的认证方式
            stmt = select(UserAuthMethod).where(
                UserAuthMethod.provider == "qq",
                UserAuthMethod.provider_user_id == qq_id
            )
            auth_method = db.exec(stmt).first()
            
            if auth_method:
                # 已存在认证方式,直接登录
                logger.info(f"✅ [Auth] Existing user login: {auth_method.user_id}")
                user_id = auth_method.user_id
            else:
                # 首次QQ登录,创建新用户
                user_id = User.generate_next_id()
                logger.info(f"✨ [Auth] Creating new user for QQ {qq_id} -> user_id={user_id}")
                
                user = User(
                    user_id=user_id,
                    nickname=nickname
                )
                db.add(user)
                
                # 创建认证方式
                auth_method = UserAuthMethod(
                    user_id=user_id,
                    provider="qq",
                    provider_user_id=qq_id,
                    is_primary=True
                )
                db.add(auth_method)
            
            # 创建持久化 Session
            session = UserSession.create(
                user_id=user_id,
                provider="qq",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
            db.add(session)
            
            # Extract ID while in session
            session_id = session.session_id
        
        # Determine redirect URL
        target_url = f"{WEB_BASE_URL}/"
        if redirect and redirect.startswith("/"):
             target_url = f"{WEB_BASE_URL}{redirect}"
        
        resp = RedirectResponse(url=target_url)
        
        if session_id:
            set_session_cookie(resp, session_id)
        
        return resp
        
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=400, content={"error": "链接已过期,请重新获取"})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=400, content={"error": "无效的登录链接"})
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "登录失败,请稍后重试"})


@router.get("/me")
async def get_current_user_info(request: Request):
    """获取当前登录用户信息"""
    from web.dependencies import get_current_user
    session_data = get_current_user(request)
    
    if not session_data:
        return {"authenticated": False, "user": None}
    
    with session_scope() as db:
        user = db.get(User, session_data["user_id"])
        if not user:
            return {"authenticated": False, "user": None}
        
        return {
            "authenticated": True,
            "user": {
                "user_id": user.user_id,
                "nickname": user.nickname,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "trust_score": user.trust_score
            }
        }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """登出"""
    from web.session import delete_session
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        delete_session(session_id)
    
    resp = JSONResponse(content={"status": "logged_out"})
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp
