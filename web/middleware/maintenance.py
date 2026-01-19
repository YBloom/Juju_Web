"""
Maintenance Mode Middleware
维护模式中间件

功能：
- 当 MAINTENANCE_MODE=1 时拦截普通请求，返回维护页面
- 已登录 admin（有有效 admin_session cookie）可以绕过维护模式，正常访问网站
- 白名单：/health, /static/, /admin, /admin/*
"""
import os
from pathlib import Path
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """维护模式中间件"""
    
    def __init__(self, app, maintenance_page_path: Path):
        super().__init__(app)
        self.maintenance_page_path = maintenance_page_path
        self._maintenance_html = None
    
    def _is_maintenance_mode(self) -> bool:
        """检查是否处于维护模式"""
        mode = os.getenv("MAINTENANCE_MODE", "0").strip().lower()
        return mode in {"1", "true", "yes", "on"}
    
    def _load_maintenance_page(self) -> str:
        """加载维护页面HTML"""
        if self._maintenance_html is None:
            if self.maintenance_page_path.exists():
                self._maintenance_html = self.maintenance_page_path.read_text(encoding="utf-8")
            else:
                # 降级方案：简单的HTML
                self._maintenance_html = """
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>维护中</title>
                    <style>
                        body { font-family: sans-serif; text-align: center; padding: 50px; }
                        h1 { color: #637E60; }
                    </style>
                </head>
                <body>
                    <h1>🛠️ 服务器维护中</h1>
                    <p>我们正在进行系统维护，预计很快恢复。</p>
                    <p>感谢您的耐心等待！</p>
                </body>
                </html>
                """
        return self._maintenance_html
    
    def _has_admin_session(self, request: Request) -> bool:
        """检查请求是否有有效的 admin session"""
        # 延迟导入避免循环依赖
        from web.routers.admin import has_admin_session
        return has_admin_session(request)
    
    def _should_bypass(self, path: str) -> bool:
        """判断路径是否应该绕过维护检查（白名单路径）"""
        bypass_prefixes = (
            "/health",       # 健康检查
            "/static/",      # 静态资源
            "/admin",        # 管理后台（包括 /admin 和 /admin/*）
        )
        return path.startswith(bypass_prefixes)
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 如果不在维护模式，直接放行
        if not self._is_maintenance_mode():
            return await call_next(request)
        
        path = request.url.path
        
        # 白名单路径直接放行
        if self._should_bypass(path):
            return await call_next(request)
        
        # 检查是否有有效的 admin session
        if self._has_admin_session(request):
            return await call_next(request)
        
        # 未登录 admin：返回维护页面
        # API 请求返回 JSON，HTML 请求返回维护页面
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "服务器维护中",
                    "message": "我们正在进行系统维护，预计很快恢复。感谢您的耐心等待！",
                    "maintenance": True,
                    "hint": "管理员请访问 /admin 登录后继续使用"
                }
            )
        
        # HTML 请求返回维护页面
        html = self._load_maintenance_page()
        return HTMLResponse(content=html, status_code=503)
