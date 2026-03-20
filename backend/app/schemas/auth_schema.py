"""
认证相关 Pydantic Schemas
"""
from pydantic import BaseModel, EmailStr, field_validator
import re


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str
    email: EmailStr
    password: str
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 50:
            raise ValueError("用户名长度必须在 3-50 个字符之间")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 20:
            raise ValueError("密码长度必须在 8-20 个字符之间")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("密码必须同时包含字母和数字")
        return v


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserProfileUpdate(BaseModel):
    """用户资料更新请求（仅允许修改用户名、邮箱）"""
    username: str
    email: EmailStr

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        username = v.strip()
        if len(username) < 3 or len(username) > 50:
            raise ValueError("用户名长度必须在 3-50 个字符之间")
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return username


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 20:
            raise ValueError("新密码长度必须在 8-20 个字符之间")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("新密码必须同时包含字母和数字")
        return v


class ForgotPasswordRequest(BaseModel):
    """忘记密码重置请求（轻量方案：用户名 + 邮箱 + 新密码）"""
    username: str
    email: EmailStr
    new_password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 50:
            raise ValueError("用户名长度必须在 3-50 个字符之间")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 20:
            raise ValueError("新密码长度必须在 8-20 个字符之间")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("新密码必须同时包含字母和数字")
        return v


class AccessTokenResponse(BaseModel):
    """仅 Access Token 响应 (用于刷新)"""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: str
    role: str
    created_at: str
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """登录响应（仅返回 AT，RT 通过 HttpOnly Cookie 下发）"""
    access_token: str
    user: UserResponse
    token_type: str = "bearer"
