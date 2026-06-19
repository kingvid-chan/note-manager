"""分享服务层 — 创建、列表、撤销分享链接。

纯 SQLAlchemy 操作，不依赖 FastAPI，由路由层调用。
"""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from ..models import Note, ShareLink, ActivityLog


# ── 常量 ────────────────────────────────────────────────────
DEFAULT_EXPIRY_HOURS = 168  # 7 天


# ═══════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════

def create_share(
    db: Session,
    note_id: int,
    user_id: int,
    expires_in_hours: int | None = DEFAULT_EXPIRY_HOURS,
) -> ShareLink | None:
    """为笔记创建分享链接 — 需要笔记所有权。

    Args:
        db: 数据库会话。
        note_id: 笔记主键。
        user_id: 当前用户 ID。
        expires_in_hours: 有效小时数，None 表示永不过期，默认 168（7 天）。

    Returns:
        新创建的 ShareLink 对象，无权限返回 None。
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None or note.user_id != user_id:
        return None

    expires_at = None
    if expires_in_hours is not None:
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

    share = ShareLink(
        token=uuid4().hex,
        note_id=note_id,
        created_by=user_id,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(share)
    db.flush()

    # ActivityLog
    db.add(ActivityLog(
        user_id=user_id,
        action="create_share",
        target_type="share",
        target_id=share.id,
    ))
    db.commit()
    db.refresh(share)
    return share


def list_user_shares(db: Session, user_id: int) -> list[ShareLink]:
    """列出当前用户创建的所有分享链接，含关联笔记标题。

    按创建时间倒序排列。
    """
    return (
        db.query(ShareLink)
        .options(joinedload(ShareLink.note))
        .filter(ShareLink.created_by == user_id)
        .order_by(ShareLink.created_at.desc())
        .all()
    )


def revoke_share(db: Session, share_id: int, user_id: int) -> bool:
    """撤销（软关闭）分享链接 — 需要分享创建者所有权。

    Args:
        db: 数据库会话。
        share_id: 分享链接主键。
        user_id: 当前用户 ID。

    Returns:
        True 表示撤销成功，False 表示不存在或非所有者。
    """
    share = db.query(ShareLink).filter(ShareLink.id == share_id).first()
    if share is None or share.created_by != user_id:
        return False

    share.is_active = False
    db.add(ActivityLog(
        user_id=user_id,
        action="revoke_share",
        target_type="share",
        target_id=share_id,
    ))
    db.commit()
    return True
