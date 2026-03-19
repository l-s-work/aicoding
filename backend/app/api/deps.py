"""
API 依赖注入函数
包含：数据库会话、当前用户获取、权限验证等
"""
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.db.database import get_db
from app.db.models import User, AccessTokenBlocklist
from app.core.security import decode_token


# HTTP Bearer Token 认证
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """
    从 JWT Token 中解析当前用户
    验证 token_version 防止被强制登出
    """
    token = credentials.credentials
    
    # 解码 Token
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
        )
    
    # 检查 Token 类型
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 类型错误",
        )
    
    user_id: int = payload.get("user_id")
    token_version: int = payload.get("token_version")
    token_jti: str | None = payload.get("jti")
    
    if not user_id or token_version is None or not token_jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 格式错误",
        )

    # 检查是否在 Access Token 拦截表中（主动退出后即时失效）
    blocked_result = await db.execute(
        select(AccessTokenBlocklist).where(AccessTokenBlocklist.jti == token_jti)
    )
    if blocked_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已失效，请重新登录",
        )
    
    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    
    # 检查 token_version (防止强制登出)
    if user.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已失效，请重新登录",
        )
    
    # 检查账号锁定状态
    if user.lockout_until:
        lockout_time = datetime.fromisoformat(user.lockout_until)
        if datetime.utcnow() < lockout_time:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="账号已被临时锁定，请稍后再试",
            )
    
    return user


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    验证当前用户是否为管理员
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，仅管理员可访问",
        )
    return current_user


# 类型别名 (简化路由函数签名)
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
