"""
Cloudflare Turnstile 人机验证服务

用于验证前端提交的Turnstile token，防止自动化攻击和邮件资源滥用。
"""
import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

# Cloudflare Turnstile 验证端点
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str, remote_ip: Optional[str] = None) -> bool:
    """
    验证 Cloudflare Turnstile token
    
    Args:
        token: 前端提交的验证token
        remote_ip: 用户IP地址(可选,用于增强验证)
    
    Returns:
        bool: 验证是否通过
    """
    secret_key = os.getenv("TURNSTILE_SECRET_KEY")
    
    # 如果未配置密钥,记录警告并返回True(降级到IP限流)
    if not secret_key:
        logger.warning("⚠️ [Turnstile] SECRET_KEY 未配置,跳过人机验证(降级模式)")
        return True
    
    if not token:
        logger.warning("⚠️ [Turnstile] Token为空,验证失败")
        return False
    
    try:
        # 构建请求数据
        data = {
            "secret": secret_key,
            "response": token
        }
        
        # 如果提供了IP,添加到验证数据中
        if remote_ip:
            data["remoteip"] = remote_ip
        
        # 发送验证请求
        async with aiohttp.ClientSession() as session:
            async with session.post(TURNSTILE_VERIFY_URL, data=data, timeout=5) as resp:
                if resp.status != 200:
                    logger.error(f"❌ [Turnstile] API请求失败: {resp.status}")
                    return False
                
                result = await resp.json()
                
                # 验证成功
                if result.get("success"):
                    logger.info(f"✅ [Turnstile] 验证通过 (IP: {remote_ip or 'unknown'})")
                    return True
                else:
                    # 验证失败,记录错误码
                    error_codes = result.get("error-codes", [])
                    logger.warning(f"❌ [Turnstile] 验证失败: {error_codes}")
                    return False
                    
    except aiohttp.ClientError as e:
        logger.error(f"❌ [Turnstile] 网络请求异常: {e}")
        # 网络异常时降级,返回True(避免阻塞用户)
        return True
    except Exception as e:
        logger.error(f"❌ [Turnstile] 未知异常: {e}", exc_info=True)
        # 未知异常时降级
        return True


def get_site_key() -> str:
    """获取Turnstile站点密钥(公开密钥,用于前端)"""
    return os.getenv("TURNSTILE_SITE_KEY", "")


def is_turnstile_enabled() -> bool:
    """检查Turnstile是否已配置并启用"""
    return bool(os.getenv("TURNSTILE_SECRET_KEY"))
