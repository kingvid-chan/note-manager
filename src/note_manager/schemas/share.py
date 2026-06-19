"""分享相关 Pydantic schema — 请求/响应校验 (v2)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════
# 请求
# ═══════════════════════════════════════════════════════════════

class ShareCreate(BaseModel):
    """创建分享链接请求。"""
    expires_in_hours: Optional[int] = Field(
        default=168, ge=1, le=87600,  # max ~10 years
        description="有效小时数，默认 168（7 天），null 表示永不过期",
    )


# ═══════════════════════════════════════════════════════════════
# 响应
# ═══════════════════════════════════════════════════════════════

class ShareResponse(BaseModel):
    """分享链接响应。"""
    id: int
    token: str
    url: str
    note_id: int
    note_title: str = ""
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShareListResponse(BaseModel):
    """分享链接列表响应。"""
    items: list[ShareResponse]
