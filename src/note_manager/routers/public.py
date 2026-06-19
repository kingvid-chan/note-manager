"""公开分享查看 API — GET /api/public/notes/{token}。

无需认证，校验 token 有效且未过期，返回笔记完整内容。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import ShareLink

router = APIRouter(tags=["public"])


# ═══════════════════════════════════════════════════════════════
# GET /api/public/notes/{token} — 公开查看分享笔记
# ═══════════════════════════════════════════════════════════════

@router.get("/notes/{token}")
async def view_shared_note(
    token: str,
    db: Session = Depends(get_db),
):
    """通过分享 token 公开查看笔记 — 无需认证。

    校验：
    1. token 存在且 share 处于激活状态 (is_active=True)
    2. 未过期 (expires_at IS NULL 或 > 当前时间)

    返回笔记完整内容含 Markdown、作者用户名（不含邮箱等敏感信息）。
    """
    share = (
        db.query(ShareLink)
        .options(
            joinedload(ShareLink.note),
            joinedload(ShareLink.creator),
        )
        .filter(ShareLink.token == token)
        .first()
    )

    # 不存在
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )

    # 已撤销
    if not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )

    # 已过期
    if share.expires_at is not None and share.expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )

    note = share.note

    return {
        "id": note.id,
        "title": note.title,
        "content_md": note.content_md,
        "author": {
            "username": share.creator.username if share.creator else "unknown",
        },
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }
