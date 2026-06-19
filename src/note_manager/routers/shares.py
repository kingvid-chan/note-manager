"""分享 API — 创建/列表/撤销分享链接。

全部端点需要 JWT 认证 (``Depends(get_current_user)``)。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import User, Note
from ..schemas.share import ShareCreate, ShareResponse, ShareListResponse
from ..services import share_service

router = APIRouter(tags=["shares"])


def _build_url(token: str) -> str:
    """构建分享链接的完整 URL 路径。"""
    return f"{settings.BASE_PATH}/share/{token}"


# ═══════════════════════════════════════════════════════════════
# POST /api/notes/{note_id}/share — 创建分享链接
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/notes/{note_id}/share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_share(
    note_id: int,
    data: ShareCreate = ShareCreate(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为笔记创建公开分享链接。

    默认 7 天有效，设置 ``expires_in_hours`` 为 null 则永不过期。
    需要笔记所有权。
    """
    # 先查笔记是否存在
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    if note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to share this note",
        )

    share = share_service.create_share(
        db,
        note_id=note_id,
        user_id=current_user.id,
        expires_in_hours=data.expires_in_hours,
    )

    return ShareResponse(
        id=share.id,
        token=share.token,
        url=_build_url(share.token),
        note_id=share.note_id,
        note_title=note.title,
        expires_at=share.expires_at,
        is_active=share.is_active,
        created_at=share.created_at,
    )


# ═══════════════════════════════════════════════════════════════
# GET /api/shares — 用户分享列表
# ═══════════════════════════════════════════════════════════════

@router.get("/shares/", response_model=ShareListResponse)
async def list_shares(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户创建的所有分享链接。"""
    shares = share_service.list_user_shares(db, current_user.id)
    items = [
        ShareResponse(
            id=s.id,
            token=s.token,
            url=_build_url(s.token),
            note_id=s.note_id,
            note_title=s.note.title if s.note else "",
            expires_at=s.expires_at,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in shares
    ]
    return ShareListResponse(items=items)


# ═══════════════════════════════════════════════════════════════
# DELETE /api/shares/{share_id} — 撤销分享
# ═══════════════════════════════════════════════════════════════

@router.delete(
    "/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_share(
    share_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """撤销（关闭）分享链接 — 仅创建者可操作。

    撤销后公开访问立即失效。
    """
    from ..models import ShareLink
    share = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )
    if share.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to revoke this share",
        )

    share_service.revoke_share(db, share_id, current_user.id)
    return None
