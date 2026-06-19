"""笔记相关 Pydantic schema — 请求/响应校验 (v2)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════
# 嵌套
# ═══════════════════════════════════════════════════════════════

class TagBrief(BaseModel):
    """标签摘要 — 嵌入 NoteResponse。"""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════
# 请求
# ═══════════════════════════════════════════════════════════════

class NoteCreate(BaseModel):
    """创建笔记请求。"""
    title: str = Field(default="Untitled", max_length=256)
    content_md: str = Field(default="")
    tag_ids: Optional[list[int]] = Field(default=None)


class NoteUpdate(BaseModel):
    """更新笔记请求 — 所有字段可选，未传的保持原值。"""
    title: Optional[str] = Field(default=None, max_length=256)
    content_md: Optional[str] = Field(default=None)
    tag_ids: Optional[list[int]] = Field(default=None)


# ═══════════════════════════════════════════════════════════════
# 响应
# ═══════════════════════════════════════════════════════════════

class NoteResponse(BaseModel):
    """笔记详情响应。"""
    id: int
    title: str
    content_md: str
    tags: list[TagBrief] = []
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NoteListResponse(BaseModel):
    """笔记分页列表响应。"""
    items: list[NoteResponse]
    total: int
    page: int
    per_page: int
