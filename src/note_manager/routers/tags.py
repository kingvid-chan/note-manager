"""标签 API — 列表 / 为笔记添加标签 / 移除标签。

全部端点需要 JWT 认证 (``Depends(get_current_user)``)。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User, Note, Tag
from ..schemas.tag import TagCreate, TagResponse, TagListResponse
from ..services import tag_service

router = APIRouter(tags=["tags"])


# ═══════════════════════════════════════════════════════════════
# GET /api/tags — 用户标签列表（含使用计数）
# ═══════════════════════════════════════════════════════════════

@router.get("/tags/", response_model=TagListResponse)
async def list_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的所有标签，每项含 ``note_count`` 使用计数。"""
    items = tag_service.list_user_tags(db, current_user.id)
    return TagListResponse(
        items=[TagResponse(**item) for item in items]
    )


# ═══════════════════════════════════════════════════════════════
# POST /api/notes/{note_id}/tags — 为笔记添加标签
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/notes/{note_id}/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_tag_to_note(
    note_id: int,
    data: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为指定笔记添加标签 — 标签不存在则自动创建。

    需要笔记所有权。
    """
    # 校验笔记所有权
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    if note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this note",
        )

    # 查找或创建标签
    tag = tag_service.get_or_create_tag(db, current_user.id, data.name)

    # 关联
    tag_service.add_tag_to_note(db, note_id, tag.id, current_user.id)

    # 计算 note_count
    items = tag_service.list_user_tags(db, current_user.id)
    note_count = next((item["note_count"] for item in items if item["id"] == tag.id), 0)

    return TagResponse(id=tag.id, name=tag.name, note_count=note_count)


# ═══════════════════════════════════════════════════════════════
# DELETE /api/notes/{note_id}/tags/{tag_id} — 移除标签关联
# ═══════════════════════════════════════════════════════════════

@router.delete(
    "/notes/{note_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_tag_from_note(
    note_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从笔记移除标签 — 只移除关联关系，不删除标签本身。

    需要笔记所有权。
    """
    # 校验笔记所有权
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    if note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this note",
        )

    # 校验关联是否存在
    from ..models import NoteTag
    link = db.query(NoteTag).filter(
        NoteTag.note_id == note_id, NoteTag.tag_id == tag_id
    ).first()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not associated with this note",
        )

    tag_service.remove_tag_from_note(db, note_id, tag_id, current_user.id)
    return None
