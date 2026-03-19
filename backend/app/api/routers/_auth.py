"""
认证路由：注册、登录、刷新 Token、登出
"""
from datetime import datetime, timedelta
import hashlib

from fastapi import APIRouter, HTTPException, status, Response, Cookie, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
import jwt

from app.api.deps import DatabaseSession, CurrentUser
from app.db.models import User, RefreshToken, AccessTokenBlocklist
from app.schemas.auth_schema import (
    UserRegister, UserLogin, TokenResponse, 
    AccessTokenResponse, UserResponse
)
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token
)

router = APIRouter(prefix="/auth", tags=["认证"])
bearer_scheme = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: DatabaseSession):
    """
    用户注册
    
    - 校验用户名和邮箱唯一性
    - 密码格式校验（Pydantic 已处理）
    - 密码 Bcrypt 哈希存储
    """
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被注册"
        )
    
    # 创建新用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="client",  # 默认为普通用户
        token_version=1,
        failed_login_attempts=0,
    )
    
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户创建失败，请重试"
        )
    
    return new_user


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, response: Response, db: DatabaseSession):
    """
    用户登录
    
    - 验证账号密码
    - 防暴力破解：5次失败锁定10分钟
    - 返回 Access Token（响应体）+ Refresh Token（HttpOnly Cookie）
    """
    # 查询用户
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()
    
    # 验证失败处理 (统一错误信息，防止用户名枚举)
    async def handle_failed_login(user_obj: User | None):
        if user_obj:
            user_obj.failed_login_attempts += 1
            
            # 5次失败锁定10分钟
            if user_obj.failed_login_attempts >= 5:
                lockout_time = datetime.utcnow() + timedelta(minutes=10)
                user_obj.lockout_until = lockout_time.isoformat()
                user_obj.failed_login_attempts = 0
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="登录失败次数过多，账号已被临时锁定10分钟"
                )
            
            await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    
    if not user:
        await handle_failed_login(None)
    
    # 检查账号锁定状态
    if user.lockout_until:
        lockout_time = datetime.fromisoformat(user.lockout_until)
        if datetime.utcnow() < lockout_time:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="账号已被临时锁定，请稍后再试"
            )
        else:
            # 锁定时间已过，清除锁定
            user.lockout_until = None
    
    # 验证密码
    if not verify_password(credentials.password, user.password_hash):
        await handle_failed_login(user)
    
    # 登录成功：重置失败计数
    user.failed_login_attempts = 0
    user.lockout_until = None
    # 兼容历史数据：旧版本使用 customer，统一迁移为 client
    if user.role == "customer":
        user.role = "client"
    await db.commit()
    
    # 生成 Token
    token_payload = {
        "user_id": user.id,
        "role": user.role,
        "token_version": user.token_version,
    }
    
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token({"user_id": user.id})
    
    # 存储 Refresh Token 哈希 (SHA-256)
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at.isoformat(),
    )
    db.add(refresh_token_record)
    await db.commit()
    
    # 将 Refresh Token 写入 HttpOnly Cookie（安全，JS 无法访问）
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # 生产环境应为 True (HTTPS)
        samesite="strict",
        max_age=7 * 24 * 60 * 60,  # 7天
    )
    
    return TokenResponse(
        access_token=access_token,
        user=user,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_access_token(
    db: DatabaseSession,
    refresh_token: str | None = Cookie(default=None),
):
    """
    刷新 Access Token
    
    - 前端 Access Token 过期时自动调用
    - 验证 Refresh Token 有效性
    - 签发新的 Access Token
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Refresh Token，请重新登录"
        )

    try:
        payload = decode_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token 已过期，请重新登录"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Refresh Token"
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 类型错误"
        )
    
    user_id = payload.get("user_id")
    
    # 检查 Refresh Token 是否在数据库中 (未被撤销)
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token 已失效，请重新登录"
        )

    # 兜底校验数据库过期时间，避免脏数据导致误通过
    if datetime.utcnow() >= datetime.fromisoformat(token_record.expires_at):
        await db.execute(delete(RefreshToken).where(RefreshToken.id == token_record.id))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token 已过期，请重新登录"
        )
    
    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    
    # 签发新的 Access Token
    access_token = create_access_token({
        "user_id": user.id,
        "role": user.role,
        "token_version": user.token_version,
    })
    
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: CurrentUser,
    db: DatabaseSession,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    refresh_token: str | None = Cookie(default=None),
):
    """
    用户登出
    
    - 当前 AT 的 jti 写入拦截表（立即失效）
    - 删除当前 Refresh Token (单点登出)
    """
    # 1) 将当前 Access Token 的 jti 写入拦截表，实现“主动登出后立即失效”
    access_payload = decode_token(credentials.credentials)
    access_jti = access_payload.get("jti")
    access_exp = access_payload.get("exp")
    if access_jti and access_exp:
        if isinstance(access_exp, (int, float)):
            expires_at = datetime.utcfromtimestamp(access_exp).isoformat()
        elif isinstance(access_exp, datetime):
            expires_at = access_exp.isoformat()
        else:
            # 异常场景兜底：无法解析 exp 时给一个短期时间，避免 token 长期可用
            expires_at = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        db.add(
            AccessTokenBlocklist(
                user_id=current_user.id,
                jti=access_jti,
                expires_at=expires_at,
            )
        )

    # 2) 删除当前设备对应的 Refresh Token（精准单设备退出）
    if refresh_token:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await db.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == current_user.id,
                RefreshToken.token_hash == token_hash
            )
        )

    await db.commit()
    response.delete_cookie("refresh_token")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all_devices(
    response: Response,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    退出所有设备
    
    - 增加 token_version，使所有已签发的 Token 失效
    - 删除所有 Refresh Token
    """
    # 增加 token_version
    current_user.token_version += 1
    
    # 删除该用户所有 Refresh Token
    await db.execute(
        delete(RefreshToken).where(RefreshToken.user_id == current_user.id)
    )
    
    await db.commit()
    response.delete_cookie("refresh_token")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """获取当前登录用户信息"""
    return current_user
