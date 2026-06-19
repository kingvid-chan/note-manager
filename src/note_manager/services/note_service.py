"""笔记服务层 — CRUD + 分页 + 搜索 + 标签筛选。

纯 SQLAlchemy 操作，不依赖 FastAPI，由路由层调用。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from ..models import Note, Tag, NoteTag, ActivityLog


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════

def _log(db: Session, user_id: int, action: str, target_type: str, target_id: int) -> None:
    """记录操作到 ActivityLog。"""
    db.add(ActivityLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
    ))


def _sync_tags(db: Session, note_id: int, tag_ids: list[int]) -> None:
    """将笔记的标签关联替换为给定的 tag_ids 集合。

    删除不在新集合中的旧关联，添加新关联（幂等）。
    """
    # 删除不再需要的关联
    existing_ids = {
        row[0] for row in
        db.query(NoteTag.tag_id).filter(NoteTag.note_id == note_id).all()
    }
    to_remove = existing_ids - set(tag_ids)
    if to_remove:
        db.query(NoteTag).filter(
            and_(
                NoteTag.note_id == note_id,
                NoteTag.tag_id.in_(to_remove),
            )
        ).delete(synchronize_session=False)

    # 添加新关联（幂等 — 已存在的忽略）
    to_add = set(tag_ids) - (existing_ids - to_remove)
    for tag_id in to_add:
        if not db.query(NoteTag).filter(
            and_(NoteTag.note_id == note_id, NoteTag.tag_id == tag_id)
        ).first():
            db.add(NoteTag(note_id=note_id, tag_id=tag_id))


# ═══════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════

def create_note(
    db: Session,
    user_id: int,
    title: str = "Untitled",
    content_md: str = "",
    tag_ids: Optional[list[int]] = None,
) -> Note:
    """创建笔记并关联标签。

    Args:
        db: 数据库会话。
        user_id: 笔记所有者。
        title: 标题，默认 "Untitled"。
        content_md: Markdown 正文。
        tag_ids: 初始标签 ID 列表。

    Returns:
        新创建的 Note ORM 对象（已 refresh）。
    """
    note = Note(
        title=title,
        content_md=content_md,
        user_id=user_id,
    )
    db.add(note)
    db.flush()  # 获取 note.id

    # 关联标签
    if tag_ids:
        _sync_tags(db, note.id, tag_ids)

    _log(db, user_id, "create_note", "note", note.id)
    db.commit()
    db.refresh(note)
    return note


def get_note(db: Session, note_id: int, user_id: int) -> Note | None:
    """获取笔记详情 — 仅所有者可查看。

    Args:
        db: 数据库会话。
        note_id: 笔记主键。
        user_id: 当前用户 ID（用于所有权校验）。

    Returns:
        匹配的 Note 对象，非所有者或不存在返回 None。
    """
    note = (
        db.query(Note)
        .options(joinedload(Note.tags))
        .filter(Note.id == note_id)
        .first()
    )
    if note is None or note.user_id != user_id:
        return None
    return note


def list_notes(
    db: Session,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    tag: Optional[str] = None,
) -> tuple[list[Note], int]:
    """分页列出当前用户的笔记，支持搜索和标签筛选。

    Args:
        db: 数据库会话。
        user_id: 笔记所有者。
        page: 页码（1-based）。
        per_page: 每页条数。
        search: 关键词，LIKE 匹配标题和正文。
        tag: 逗号分隔的标签名列表，AND 逻辑（笔记必须包含所有指定标签）。

    Returns:
        (笔记列表, 总条数) 元组。
    """
    query = db.query(Note).options(joinedload(Note.tags)).filter(Note.user_id == user_id)

    # 关键词搜索 — 标题或内容 LIKE
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Note.title.ilike(like), Note.content_md.ilike(like))
        )

    # 标签筛选 — AND 逻辑：笔记必须包含所有指定标签
    if tag:
        tag_names = [t.strip() for t in tag.split(",") if t.strip()]
        if tag_names:
            # 查询当前用户的所有匹配标签
            user_tags = (
                db.query(Tag.id)
                .filter(
                    and_(Tag.user_id == user_id, Tag.name.in_(tag_names))
                )
                .all()
            )
            tag_ids = [row[0] for row in user_tags]

            # 如果用户没有这些标签，返回空
            if len(tag_ids) != len(tag_names):
                return [], 0

            for tid in tag_ids:
                sub = (
                    db.query(NoteTag.note_id)
                    .filter(NoteTag.tag_id == tid)
                    .subquery()
                )
                query = query.filter(Note.id.in_(sub))

    # 排序 + 总数
    total = query.count()
    query = query.order_by(desc(Note.created_at))

    # 分页
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()

    return items, total


def update_note(
    db: Session,
    note_id: int,
    user_id: int,
    title: Optional[str] = None,
    content_md: Optional[str] = None,
    tag_ids: Optional[list[int]] = None,
) -> Note | None:
    """更新笔记 — 仅所有者可操作。

    传入 None 的字段保持原值不变；tag_ids 为 None 时不清除现有标签。

    Args:
        db: 数据库会话。
        note_id: 笔记主键。
        user_id: 当前用户 ID。
        title: 新标题（None 表示不修改）。
        content_md: 新正文（None 表示不修改）。
        tag_ids: 新标签 ID 列表（None 表示不修改）。

    Returns:
        更新后的 Note 对象，非所有者或不存在返回 None。
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None or note.user_id != user_id:
        return None

    if title is not None:
        note.title = title
    if content_md is not None:
        note.content_md = content_md

    note.updated_at = datetime.utcnow()

    if tag_ids is not None:
        _sync_tags(db, note_id, tag_ids)

    _log(db, user_id, "update_note", "note", note_id)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note_id: int, user_id: int) -> bool:
    """真删除笔记 — 仅所有者可操作。

    Args:
        db: 数据库会话。
        note_id: 笔记主键。
        user_id: 当前用户 ID。

    Returns:
        True 表示删除成功，False 表示不存在或非所有者。
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None or note.user_id != user_id:
        return False

    _log(db, user_id, "delete_note", "note", note_id)

    # 先删除关联的 note_tags（外键 ON DELETE CASCADE 会处理，但显式处理更安全）
    db.query(NoteTag).filter(NoteTag.note_id == note_id).delete(synchronize_session=False)
    db.delete(note)
    db.commit()
    return True
