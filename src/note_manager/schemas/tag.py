"""标签相关 Pydantic schema — 请求/响应校验 (v2)。"""

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════
# 请求
# ═══════════════════════════════════════════════════════════════

class TagCreate(BaseModel):
    """创建/添加标签请求。"""
    name: str = Field(..., min_length=1, max_length=64)


# ═══════════════════════════════════════════════════════════════
# 响应
# ═══════════════════════════════════════════════════════════════

class TagResponse(BaseModel):
    """标签响应 — 含使用计数。"""
    id: int
    name: str
    note_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TagListResponse(BaseModel):
    """标签列表响应。"""
    items: list[TagResponse]
