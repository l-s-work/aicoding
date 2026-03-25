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
from app.db.models import User, RefreshToken, AccessTokenBlocklist, AccountRecoveryRequest
from app.schemas.auth_schema import (
    UserRegister, UserLogin, ForgotPasswordRequest, TokenResponse,
    AccessTokenResponse, UserResponse, UserProfileUpdate, ChangePasswordRequest, AccountRecoveryApplyRequest
)
from app.core.config import settings
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
        is_active=1,
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


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(payload: ForgotPasswordRequest, db: DatabaseSession):
    """
    忘记密码（轻量重置）

    - 通过「用户名 + 邮箱」校验身份（不引入邮件服务，保持轻量）
    - 校验通过后更新密码哈希
    - 强制旧会话失效：token_version + 1，并清理 refresh_tokens
    - 无论账户是否存在，都返回 204，避免账号枚举
    """
    result = await db.execute(
        select(User).where(
            User.username == payload.username,
            User.email == payload.email,
        )
    )
    user = result.scalar_one_or_none()

    # 防止账号枚举：未命中用户也返回 204
    if not user:
        return

    user.password_hash = hash_password(payload.new_password)
    user.failed_login_attempts = 0
    user.lockout_until = None
    user.token_version += 1

    # 清理该用户所有 Refresh Token，避免旧会话继续换发新 AT
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()


@router.post("/recovery-request", status_code=status.HTTP_201_CREATED)
async def apply_account_recovery(payload: AccountRecoveryApplyRequest, db: DatabaseSession):
    """
    封禁账号恢复申请

    - 用户在登录页收到“账号被封禁”提示后可发起
    - 同一账号同一时刻仅允许一个 pending 申请，避免重复提交
    """
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    if user.is_active == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前账号状态正常，无需申请恢复"
        )

    pending_request = await db.execute(
        select(AccountRecoveryRequest).where(
            AccountRecoveryRequest.user_id == user.id,
            AccountRecoveryRequest.status == "pending",
        )
    )
    if pending_request.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="你已有待处理的恢复申请，请勿重复提交"
        )

    request_record = AccountRecoveryRequest(
        user_id=user.id,
        username=user.username,
        reason=payload.reason.strip(),
        status="pending",
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(request_record)
    await db.commit()

    return {"message": "恢复申请已提交，请等待管理员处理"}


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

    if user.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被封禁，请联系管理员"
        )
    
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
        # 通过配置控制，避免把“是否 HTTPS”硬编码到业务逻辑里。
        secure=settings.COOKIE_SECURE,
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


@router.put("/me", response_model=UserResponse)
async def update_current_user_info(
    payload: UserProfileUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """
    修改当前登录用户资料

    - 仅允许修改用户名和邮箱
    - role 等敏感字段不允许客户端修改
    """
    # 用户名唯一性检查（排除自己）
    username_exists = await db.execute(
        select(User).where(
            User.username == payload.username,
            User.id != current_user.id
        )
    )
    if username_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )

    # 邮箱唯一性检查（排除自己）
    email_exists = await db.execute(
        select(User).where(
            User.email == payload.email,
            User.id != current_user.id
        )
    )
    if email_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被使用"
        )

    current_user.username = payload.username
    current_user.email = payload.email

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: DatabaseSession,
    current_user: CurrentUser,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    修改密码（修改后强制重新登录）

    - 验证旧密码
    - 更新密码哈希
    - token_version + 1 使历史 Access Token 全部失效
    - 清理所有 Refresh Token 并删除 Cookie
    """
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确"
        )

    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同"
        )

    current_user.password_hash = hash_password(payload.new_password)
    current_user.token_version += 1
    current_user.failed_login_attempts = 0
    current_user.lockout_until = None

    # 立即拉黑本次请求的 Access Token，避免窗口期继续访问
    access_payload = decode_token(credentials.credentials)
    access_jti = access_payload.get("jti")
    access_exp = access_payload.get("exp")
    if access_jti and access_exp:
        if isinstance(access_exp, (int, float)):
            expires_at = datetime.utcfromtimestamp(access_exp).isoformat()
        elif isinstance(access_exp, datetime):
            expires_at = access_exp.isoformat()
        else:
            expires_at = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        db.add(
            AccessTokenBlocklist(
                user_id=current_user.id,
                jti=access_jti,
                expires_at=expires_at,
            )
        )

    # 清理所有 Refresh Token，要求所有设备重新登录
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == current_user.id))
    await db.commit()

    response.delete_cookie("refresh_token")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
