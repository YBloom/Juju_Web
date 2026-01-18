"""
认证路由 - 邮箱登录/注册 + QQ Magic Link
"""
from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from services.db.models import User, UserSession, EmailVerification
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
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Config
JWT_SECRET = os.getenv("JWT_SECRET", "musicalbot-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
SESSION_COOKIE_NAME = "mb_session"
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://yyj.yaobii.com")


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


def get_session_from_cookie(request: Request) -> Optional[UserSession]:
    """从 Cookie 获取 Session"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    
    with session_scope() as db:
        session = db.get(UserSession, session_id)
        if session and not session.is_expired():
            return session
    return None


def set_session_cookie(response: Response, session: UserSession):
    """设置 Session Cookie"""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=30 * 24 * 60 * 60,  # 30 天
        httponly=True,
        samesite="lax",
        secure=True
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


# === Endpoints ===

@router.post("/email/send-code")
async def send_email_code(req: EmailSendCodeRequest):
    """发送邮箱验证码"""
    email = req.email.lower().strip()
    purpose = req.purpose
    
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
            now = datetime.now(ZoneInfo("Asia/Shanghai"))
            if (now - recent.created_at).seconds < 60:
                return JSONResponse(
                    status_code=429,
                    content={"error": "发送过于频繁，请稍后再试", "wait_seconds": 60}
                )
        
        # 创建验证码
        verification = EmailVerification.create(email, purpose)
        db.add(verification)
    
    # 发送邮件
    success = await send_verification_code(email, verification.code, purpose)
    
    if success:
        return {"status": "ok", "message": "验证码已发送到您的邮箱"}
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "邮件发送失败，请稍后重试"}
        )


@router.post("/email/register")
async def email_register(req: EmailVerifyRequest, request: Request, response: Response):
    """邮箱注册"""
    email = req.email.lower().strip()
    code = req.code
    password = req.password
    
    if not password or len(password) < 6:
        return JSONResponse(status_code=400, content={"error": "密码至少6位"})
    
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
        stmt = select(User).where(User.email == email)
        if db.exec(stmt).first():
            return JSONResponse(status_code=400, content={"error": "此邮箱已注册"})
        
        # 创建用户
        user_id = f"email_{secrets.token_hex(8)}"
        user = User(
            user_id=user_id,
            email=email,
            auth_provider="email",
            auth_id=email,
            nickname=email.split("@")[0]
        )
        
        # 存储密码哈希到 extra_json
        user.extra_json = {"password_hash": hash_password(password)}
        
        db.add(user)
        
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
    
    # 发送欢迎邮件
    await send_welcome_email(email)
    
    # 设置 Cookie
    resp = JSONResponse(content={
        "status": "ok",
        "message": "注册成功",
        "user": {"user_id": user_id, "email": email}
    })
    set_session_cookie(resp, session)
    
    logger.info(f"✨ [注册] 新用户注册: {email}")
    return resp


@router.post("/email/login")
async def email_login(req: EmailLoginRequest, request: Request, response: Response):
    """邮箱密码登录"""
    email = req.email.lower().strip()
    password = req.password
    
    with session_scope() as db:
        stmt = select(User).where(User.email == email)
        user = db.exec(stmt).first()
        
        if not user:
            return JSONResponse(status_code=400, content={"error": "邮箱未注册"})
        
        # 验证密码
        password_hash = user.extra_json.get("password_hash") if user.extra_json else None
        if not password_hash or not verify_password(password, password_hash):
            return JSONResponse(status_code=400, content={"error": "密码错误"})
        
        # 创建 Session
        session = UserSession.create(
            user_id=user.user_id,
            provider="email",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(session)
    
    resp = JSONResponse(content={
        "status": "ok",
        "message": "登录成功",
        "user": {"user_id": user.user_id, "email": email}
    })
    set_session_cookie(resp, session)
    
    logger.info(f"🔐 [登录] 用户登录: {email}")
    return resp


@router.post("/email/reset-password")
async def reset_password(req: PasswordResetRequest):
    """重置密码"""
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
        
        # 查找用户
        stmt = select(User).where(User.email == email)
        user = db.exec(stmt).first()
        if not user:
            return JSONResponse(status_code=400, content={"error": "用户不存在"})
        
        # 更新密码
        if not user.extra_json:
            user.extra_json = {}
        user.extra_json["password_hash"] = hash_password(new_password)
        db.add(user)
        
        # 标记验证码已使用
        verification.used = True
        db.add(verification)
    
    logger.info(f"🔑 [密码重置] 用户重置密码: {email}")
    return {"status": "ok", "message": "密码重置成功，请重新登录"}


# === QQ Magic Link ===

@router.get("/magic-link")
async def login_with_magic_link(token: str, request: Request, response: Response):
    """QQ Magic Link 登录"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        qq_id = payload.get("qq_id")
        nickname = payload.get("nickname", "User")
        
        if not qq_id:
            raise HTTPException(status_code=400, detail="Invalid Token Payload")
        
        logger.info(f"🔐 [Auth] Magic Link Login: QQ {qq_id}")
        
        with session_scope() as db:
            user = db.get(User, qq_id)
            if not user:
                logger.info(f"✨ [Auth] Creating new user for QQ {qq_id}")
                user = User(
                    user_id=qq_id,
                    nickname=nickname,
                    auth_provider="qq",
                    auth_id=qq_id
                )
                db.add(user)
            else:
                if nickname and nickname != "User" and not user.nickname:
                    user.nickname = nickname
                if not user.auth_provider:
                    user.auth_provider = 'qq'
                    user.auth_id = qq_id
                db.add(user)
            
            # 创建持久化 Session
            session = UserSession.create(
                user_id=qq_id,
                provider="qq",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
            db.add(session)
        
        resp = RedirectResponse(url=f"{WEB_BASE_URL}/")
        set_session_cookie(resp, session)
        return resp
        
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=400, content={"error": "链接已过期，请重新获取"})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=400, content={"error": "无效的登录链接"})
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "登录失败，请稍后重试"})


@router.get("/me")
async def get_current_user_info(request: Request):
    """获取当前登录用户信息"""
    session = get_session_from_cookie(request)
    if not session:
        return {"authenticated": False, "user": None}
    
    with session_scope() as db:
        user = db.get(User, session.user_id)
        if not user:
            return {"authenticated": False, "user": None}
        
        return {
            "authenticated": True,
            "user": {
                "user_id": user.user_id,
                "nickname": user.nickname,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "trust_score": user.trust_score,
                "auth_provider": user.auth_provider
            }
        }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """登出"""
    session = get_session_from_cookie(request)
    if session:
        with session_scope() as db:
            db.delete(session)
    
    resp = JSONResponse(content={"status": "logged_out"})
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp
