"""标签服务层 — 创建、列表、关联/取消关联笔记。

纯 SQLAlchemy 操作，不依赖 FastAPI，由路由层调用。
"""

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..models import Note, Tag, NoteTag, ActivityLog


# ═══════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════

def get_or_create_tag(db: Session, user_id: int, name: str) -> Tag:
    """查找用户已有标签，不存在则创建。

    Args:
        db: 数据库会话。
        user_id: 标签所有者。
        name: 标签名（前后空格会被去除）。

    Returns:
        已存在或新创建的 Tag 对象。

    Raises:
        ValueError: 标签名为空字符串。
    """
    name = name.strip()
    if not name:
        raise ValueError("Tag name cannot be empty")

    tag = db.query(Tag).filter(
        and_(Tag.user_id == user_id, Tag.name == name)
    ).first()

    if tag is None:
        tag = Tag(name=name, user_id=user_id)
        db.add(tag)
        db.flush()

    return tag


def list_user_tags(db: Session, user_id: int) -> list[dict]:
    """列出当前用户的所有标签，含使用计数。

    Args:
        db: 数据库会话。
        user_id: 标签所有者。

    Returns:
        字典列表，每项含 ``id``、``name``、``note_count``。
    """
    results = (
        db.query(
            Tag.id,
            Tag.name,
            func.count(NoteTag.note_id).label("note_count"),
        )
        .outerjoin(NoteTag, NoteTag.tag_id == Tag.id)
        .filter(Tag.user_id == user_id)
        .group_by(Tag.id)
        .order_by(Tag.name)
        .all()
    )
    return [
        {"id": row[0], "name": row[1], "note_count": row[2]}
        for row in results
    ]


def add_tag_to_note(db: Session, note_id: int, tag_id: int, user_id: int) -> bool:
    """为笔记添加标签 — 需要笔记所有权。

    Args:
        db: 数据库会话。
        note_id: 笔记主键。
        tag_id: 标签主键。
        user_id: 当前用户 ID（用于所有权校验）。

    Returns:
        True 表示成功添加（或已存在），False 表示无权限或笔记不存在。
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None or note.user_id != user_id:
        return False

    # 幂等 — 已存在则忽略
    existing = db.query(NoteTag).filter(
        and_(NoteTag.note_id == note_id, NoteTag.tag_id == tag_id)
    ).first()
    if existing is None:
        db.add(NoteTag(note_id=note_id, tag_id=tag_id))
        db.commit()

    return True


def remove_tag_from_note(db: Session, note_id: int, tag_id: int, user_id: int) -> bool:
    """从笔记移除标签 — 需要笔记所有权。

    Args:
        db: 数据库会话。
        note_id: 笔记主键。
        tag_id: 标签主键。
        user_id: 当前用户 ID（用于所有权校验）。

    Returns:
        True 表示成功移除，False 表示无权限或笔记不存在。
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None or note.user_id != user_id:
        return False

    db.query(NoteTag).filter(
        and_(NoteTag.note_id == note_id, NoteTag.tag_id == tag_id)
    ).delete(synchronize_session=False)
    db.commit()
    return True


def delete_tag(db: Session, tag_id: int, user_id: int) -> bool:
    """删除标签及所有关联 — 需要标签所有权。

    Args:
        db: 数据库会话。
        tag_id: 标签主键。
        user_id: 当前用户 ID。

    Returns:
        True 表示删除成功，False 表示不存在或非所有者。
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if tag is None or tag.user_id != user_id:
        return False

    # 清除所有关联
    db.query(NoteTag).filter(NoteTag.tag_id == tag_id).delete(synchronize_session=False)
    db.delete(tag)
    db.commit()
    return True
