"""
安全模块：密码哈希 & JWT Token 生成/验证
"""
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import bcrypt

from app.core.config import settings


def hash_password(password: str) -> str:
    """
    密码哈希加密（使用 bcrypt）
    
    Args:
        password: 明文密码
        
    Returns:
        bcrypt 哈希后的密码字符串
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)  # 12轮加盐，安全性高
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配
    
    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码
        
    Returns:
        验证成功返回 True，否则 False
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    生成 Access Token (短期，2小时)
    
    Args:
        data: JWT payload (应包含: user_id, role, token_version)
        expires_delta: 过期时间增量
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 为每个 Access Token 注入 jti，便于主动登出时精准拦截
    to_encode.update({"exp": expire, "type": "access", "jti": uuid4().hex})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    生成 Refresh Token (长期，7天)
    
    Args:
        data: JWT payload (通常只包含: user_id)
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    解码并验证 JWT Token
    
    Returns:
        解码后的 payload
        
    Raises:
        jwt.PyJWTError: Token 无效或过期
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM]
    )
    return payload
