"""认证相关 Pydantic schema — 请求/响应校验。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── 请求 ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """用户注册请求。"""
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """用户登录请求（JSON 格式）。"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


# ── 响应 ─────────────────────────────────────────────────

class UserResponse(BaseModel):
    """用户公开信息（不含密码哈希）。"""
    id: int
    username: str
    email: str
    is_active: bool
    is_demo: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    """用户摘要（嵌入 token 响应）。"""
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """登录响应 — JWT token + 用户摘要。"""
    access_token: str
    token_type: str = "bearer"
    user: UserSummary
