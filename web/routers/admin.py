"""
Admin Router
提供管理后台页面和独立的 admin 认证
"""
from fastapi import APIRouter, Depends, HTTPException, Response, Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
import os
import secrets
import hashlib
import json
from typing import List, Optional
from collections import Counter
from sqlmodel import select, col
from datetime import datetime
from zoneinfo import ZoneInfo

from services.hulaquan.tables import Feedback, HulaquanSearchLog
from services.db.connection import session_scope

router = APIRouter(prefix="/admin", tags=["Admin"])
api_router = APIRouter(prefix="/api/admin", tags=["Admin API"])

# Admin 页面路径
ADMIN_PAGE = Path(__file__).parent.parent / "admin.html"

# Admin session 管理（简单的内存存储）
# key: session_token, value: True
_admin_sessions = {}

# Admin cookie 名称
ADMIN_COOKIE_NAME = "admin_session"


def verify_admin_credentials(username: str, password: str) -> bool:
    """验证 admin 账号密码（从环境变量读取）"""
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    
    if not admin_password:
        # 如果没有设置密码，出于安全考虑，拒绝登录
        return False
    
    return username == admin_username and password == admin_password


def create_admin_session() -> str:
    """创建一个新的 admin session token"""
    token = secrets.token_urlsafe(32)
    _admin_sessions[token] = True
    return token


def verify_admin_session(token: str) -> bool:
    """验证 admin session token 是否有效"""
    return token in _admin_sessions


# Admin 登录页面 HTML
ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-card {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 90%;
            max-width: 400px;
        }
        h1 { color: #333; margin-bottom: 10px; text-align: center; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 0.9rem; }
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 6px;
            color: #555;
            font-size: 0.9rem;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 1rem;
        }
        input:focus { outline: none; border-color: #637E60; }
        .btn {
            width: 100%;
            padding: 12px;
            background: #637E60;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            cursor: pointer;
        }
        .btn:hover { background: #526950; }
        .btn:disabled { background: #ccc; }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            display: none;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <h1>🛡️ Admin Login</h1>
        <div class="subtitle">管理后台登录</div>
        
        <div id="error" class="error"></div>
        
        <form id="loginForm" onsubmit="return handleLogin(event)">
            <div class="form-group">
                <label for="username">用户名</label>
                <input type="text" id="username" name="username" required autocomplete="username">
            </div>
            <div class="form-group">
                <label for="password">密码</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>
            <button type="submit" class="btn" id="submitBtn">登录</button>
        </form>
    </div>
    
    <script>
        async function handleLogin(e) {
            e.preventDefault();
            
            const btn = document.getElementById('submitBtn');
            const errorDiv = document.getElementById('error');
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            btn.disabled = true;
            btn.textContent = '登录中...';
            errorDiv.style.display = 'none';
            
            try {
                const response = await fetch('/admin/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                if (response.ok) {
                    window.location.reload();
                } else {
                    const data = await response.json();
                    errorDiv.textContent = data.detail || '登录失败';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = '网络错误';
                errorDiv.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.textContent = '登录';
            }
            
            return false;
        }
    </script>
</body>
</html>
"""


# 登录请求模型
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class Lyric(BaseModel):
    content: str
    source: str


@router.post("/login")
async def admin_login(request: AdminLoginRequest, response: Response):
    """Admin 登录 API"""
    if not verify_admin_credentials(request.username, request.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 创建 session
    session_token = create_admin_session()
    
    # 设置 cookie
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=session_token,
        max_age=86400,  # 24小时
        httponly=True,
        samesite="lax"
    )
    
    return {"success": True, "message": "登录成功"}


@router.get("/", response_class=HTMLResponse)
async def admin_page(admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """
    管理后台页面
    未登录时显示登录页面
    """
    # 检查 admin session
    if not admin_session or not verify_admin_session(admin_session):
        # 未登录：显示登录页面
        return HTMLResponse(content=ADMIN_LOGIN_HTML)
    
    # 已登录：显示 admin 页面
    if not ADMIN_PAGE.exists():
        raise HTTPException(status_code=404, detail="Admin page not found")
    
    content = ADMIN_PAGE.read_text(encoding="utf-8")
    return HTMLResponse(content=content)


# 导出验证函数供中间件使用
def has_admin_session(request: Request) -> bool:
    """检查请求是否有有效的 admin session（供中间件调用）"""
    admin_session = request.cookies.get(ADMIN_COOKIE_NAME)
    return admin_session and verify_admin_session(admin_session)


# --- 维护页面歌词管理 ---

@router.get("/lyrics")
async def get_maintenance_lyrics(admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """获取维护页面的歌词列表"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    lyrics_file = Path(__file__).parent.parent / "static" / "lyrics.json"
    if not lyrics_file.exists():
        return []
        
    try:
        return json.loads(lyrics_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read lyrics file: {str(e)}")


@router.post("/lyrics")
async def save_maintenance_lyrics(lyrics: List[Lyric], admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """保存维护页面的歌词列表"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    lyrics_file = Path(__file__).parent.parent / "static" / "lyrics.json"
    try:
        data = [lyric.dict() for lyric in lyrics]
        lyrics_file.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save lyrics file: {str(e)}")


# --- 维护模式状态管理 ---

class FeedbackReplyRequest(BaseModel):
    reply: str
    is_public: bool = False


@api_router.get("/analytics/searches")
async def get_search_analytics(admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """获取搜索聚类和热门统计。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        logs = session.exec(select(HulaquanSearchLog)).all()
        
        artist_counts = Counter()
        solo_counts = Counter()
        combo_counts = Counter()
        view_counts = Counter()
        
        for l in logs:
            if l.search_type == "view_event":
                view_counts[l.query_str] += 1
                continue
                
            if l.search_type == "co-cast" and l.artists:
                try:
                    names = json.loads(l.artists)
                    for n in names:
                        artist_counts[n] += 1
                        
                    if len(names) == 1:
                        solo_counts[names[0]] += 1
                    elif len(names) > 1:
                        combo_str = " & ".join(names)
                        combo_counts[combo_str] += 1
                except:
                    pass

        def format_top(counter, limit=20):
            return [{"name": k, "count": v} for k, v in counter.most_common(limit)]
            
        return {
            "top_artists": format_top(artist_counts),
            "top_solo": format_top(solo_counts),
            "top_combos": format_top(combo_counts),
            "top_views": format_top(view_counts)
        }


@api_router.get("/feedbacks")
async def get_feedbacks(limit: int = 50, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """获取最新的反馈列表（排除已忽略的）。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        stmt = select(Feedback).where(Feedback.is_ignored == False).order_by(col(Feedback.created_at).desc()).limit(limit)
        items = session.exec(stmt).all()
        return {
            "count": len(items),
            "results": [i.model_dump(mode='json') for i in items]
        }


@api_router.get("/feedbacks/ignored")
async def get_ignored_feedbacks(limit: int = 100, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """获取被忽略的反馈列表。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        stmt = select(Feedback).where(Feedback.is_ignored == True).order_by(col(Feedback.ignored_at).desc()).limit(limit)
        items = session.exec(stmt).all()
        return {
            "count": len(items),
            "results": [i.model_dump(mode='json') for i in items]
        }


@api_router.post("/feedback/{feedback_id}/reply")
async def reply_feedback(feedback_id: int, req: FeedbackReplyRequest, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """回复反馈并设置公开状态。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            raise HTTPException(status_code=404, detail="Not found")
            
        fb.admin_reply = req.reply
        fb.is_public = req.is_public
        if req.reply:
            fb.reply_at = datetime.now(ZoneInfo("Asia/Shanghai"))
            fb.status = "closed"
            
        session.add(fb)
        
    return {"status": "ok"}


@api_router.post("/feedback/{feedback_id}/ignore")
async def ignore_feedback(feedback_id: int, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """忽略一条反馈。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            raise HTTPException(status_code=404, detail="Not found")
            
        fb.is_ignored = True
        fb.ignored_at = datetime.now(ZoneInfo("Asia/Shanghai"))
        session.add(fb)
        
    return {"status": "ok"}


@api_router.post("/feedback/{feedback_id}/unignore")
async def unignore_feedback(feedback_id: int, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """取消忽略反馈。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            raise HTTPException(status_code=404, detail="Not found")
            
        fb.is_ignored = False
        fb.ignored_at = None
        session.add(fb)
        
    return {"status": "ok"}


@api_router.post("/feedback/{feedback_id}/resolve")
async def resolve_feedback(feedback_id: int, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """将反馈标记为已解决。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            raise HTTPException(status_code=404, detail="Not found")
            
        fb.status = "closed"
        session.add(fb)
        
    return {"status": "ok"}


@api_router.post("/feedback/{feedback_id}/reopen")
async def reopen_feedback(feedback_id: int, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """重新开始被解决的反馈。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            raise HTTPException(status_code=404, detail="Not found")
            
        fb.status = "open"
        session.add(fb)
        
    return {"status": "ok"}


@api_router.delete("/feedback/{feedback_id}")
async def delete_feedback(feedback_id: int, admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """永久删除一条反馈。"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            raise HTTPException(status_code=404, detail="Not found")
        session.delete(fb)
        
    return {"status": "ok"}


# --- 维护模式状态管理 ---

@router.get("/maintenance/status")
async def get_maintenance_status(admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """获取维护模式当前状态"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from services.maintenance_config import get_maintenance_mode
    enabled = get_maintenance_mode()
    
    return {
        "enabled": enabled,
        "status": "维护中" if enabled else "正常运行"
    }


@router.post("/maintenance/toggle")
async def toggle_maintenance_mode(admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)):
    """切换维护模式状态"""
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from services.maintenance_config import get_maintenance_mode, set_maintenance_mode
    
    # 获取当前状态并切换
    current_status = get_maintenance_mode()
    new_status = not current_status
    
    # 设置新状态
    success = set_maintenance_mode(new_status)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update maintenance mode")
    
    return {
        "success": True,
        "enabled": new_status,
        "message": f"维护模式已{'开启' if new_status else '关闭'}"
    }


# --- 日志管理 ---

@api_router.get("/logs")
async def get_logs(
    file: str, 
    request: Request,
    admin_session: str = Cookie(None, alias=ADMIN_COOKIE_NAME)
):
    """获取指定日志文件的内容"""
    # 验证 session (API 方式)
    if not admin_session or not verify_admin_session(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # 1. 项目内日志 logs/
    log_dir = Path(__file__).parent.parent.parent / "logs"
    
    # 2. Supervisor 系统日志 /var/log/musicalbot/
    sys_log_dir = Path("/var/log/musicalbot")
    
    # 允许访问的文件白名单 (对应的真实路径)
    # file_map: { requested_filename: [possible_paths] }
    file_map = {
        "bot_err.log": [sys_log_dir / "bot_err.log"],
        "bot_out.log": [sys_log_dir / "bot_out.log"],
        "web_err.log": [sys_log_dir / "web_err.log"],
        "web_out.log": [sys_log_dir / "web_out.log"],
        "auto_update.log": [log_dir / "auto_update.log"], # 假设这个在项目 logs 下
        "app.log": [log_dir / "app.log"],
        "bot.log": [log_dir / "bot.log"],
        "db.log": [log_dir / "db.log"],
    }
    
    if file not in file_map:
        raise HTTPException(status_code=400, detail="Invalid log file name")
    
    # 尝试查找文件
    target_file = None
    for path in file_map[file]:
        if path.exists():
            target_file = path
            break
            
    if not target_file:
        # Fallback for local development or if config differs
        # Try local logs dir with same name
        local_fallback = log_dir / file
        if local_fallback.exists():
            target_file = local_fallback
        else:
             return f"Log file '{file}' not found. Searched in: {[str(p) for p in file_map[file]]}"

    try:
        # 读取最后 2000 行
        from collections import deque
        
        lines = deque(maxlen=2000)
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                lines.append(line)
        
        return "".join(lines)
    except Exception as e:
        return f"Failed to read log file ({target_file}): {str(e)}"

