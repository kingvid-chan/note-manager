"""笔记 CRUD API — 列表/创建/详情/更新/删除。

全部端点需要 JWT 认证 (``Depends(get_current_user)``)。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas.note import (
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    NoteListResponse,
)
from ..services import note_service

router = APIRouter(tags=["notes"])

# ── 分页限制 ────────────────────────────────────────────────
_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


# ═══════════════════════════════════════════════════════════════
# POST / — 创建笔记
# ═══════════════════════════════════════════════════════════════

@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新笔记 — 标题默认 "Untitled"，可附带初始标签。"""
    note = note_service.create_note(
        db,
        user_id=current_user.id,
        title=data.title,
        content_md=data.content_md,
        tag_ids=data.tag_ids,
    )
    return note


# ═══════════════════════════════════════════════════════════════
# GET / — 分页列表
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=NoteListResponse)
async def list_notes(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=_DEFAULT_PER_PAGE, ge=1, le=_MAX_PER_PAGE),
    search: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页列出当前用户笔记，支持关键词搜索和标签筛选。

    - ``search``: 匹配标题和正文 (ILIKE)
    - ``tag``: 逗号分隔标签名，AND 逻辑（笔记必须包含所有指定标签）
    """
    items, total = note_service.list_notes(
        db,
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        search=search,
        tag=tag,
    )
    return NoteListResponse(
        items=[NoteResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        per_page=per_page,
    )


# ═══════════════════════════════════════════════════════════════
# GET /{id} — 笔记详情
# ═══════════════════════════════════════════════════════════════

@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取笔记详情 — 非所有者返回 404。"""
    note = note_service.get_note(db, note_id, current_user.id)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    return note


# ═══════════════════════════════════════════════════════════════
# PUT /{id} — 更新笔记
# ═══════════════════════════════════════════════════════════════

@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    data: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新笔记 — 仅所有者可操作。

    非所有者 → 403；不存在 → 404。
    """
    # 先检查所有权
    note = note_service.get_note(db, note_id, current_user.id)
    if note is None:
        # 区分 404 还是 403 — 先查笔记是否存在
        from ..models import Note
        exists = db.query(Note).filter(Note.id == note_id).first()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this note",
        )

    updated = note_service.update_note(
        db,
        note_id=note_id,
        user_id=current_user.id,
        title=data.title,
        content_md=data.content_md,
        tag_ids=data.tag_ids,
    )
    return updated


# ═══════════════════════════════════════════════════════════════
# DELETE /{id} — 删除笔记
# ═══════════════════════════════════════════════════════════════

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除笔记 — 仅所有者可操作，真删除（不可恢复）。

    非所有者 → 403；不存在 → 404。
    """
    # 先检查所有权
    note = note_service.get_note(db, note_id, current_user.id)
    if note is None:
        from ..models import Note
        exists = db.query(Note).filter(Note.id == note_id).first()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this note",
        )

    note_service.delete_note(db, note_id, current_user.id)
    return None
