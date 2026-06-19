"""测试数据工厂 — 每个函数创建独立 session、commit 后返回 ORM 对象。

这些函数可在 conftest fixture 或测试函数中直接调用。
"""

from sqlalchemy.orm import Session

from src.note_manager.models import User, Note, Tag, NoteTag, ShareLink
from src.note_manager.services.auth_service import hash_password


def create_test_user(db: Session, username: str = "factoryuser", email: str = "factory@example.com", password: str = "factory123") -> User:
    """创建测试用户，持久化到 DB 并返回 User ORM 对象。

    Args:
        db: 数据库会话。
        username: 用户名（默认 "factoryuser"）。
        email: 邮箱（默认 "factory@example.com"）。
        password: 明文密码 — 内部 bcrypt 哈希后存储。

    Returns:
        已 commit 并 refresh 的 User 对象。
    """
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_note(
    db: Session,
    user_id: int,
    title: str = "Factory Note",
    content_md: str = "Content from factory.",
    tag_ids: list[int] | None = None,
) -> Note:
    """创建测试笔记，持久化到 DB 并返回 Note ORM 对象。

    Args:
        db: 数据库会话。
        user_id: 所有者用户 ID。
        title: 笔记标题。
        content_md: Markdown 正文。
        tag_ids: 初始标签 ID 列表（可选）。

    Returns:
        已 commit 并 refresh 的 Note 对象（含 tags 关系）。
    """
    note = Note(
        title=title,
        content_md=content_md,
        user_id=user_id,
    )
    db.add(note)
    db.flush()  # 获取 note.id

    if tag_ids:
        for tag_id in tag_ids:
            if not db.query(NoteTag).filter(
                NoteTag.note_id == note.id, NoteTag.tag_id == tag_id
            ).first():
                db.add(NoteTag(note_id=note.id, tag_id=tag_id))

    db.commit()
    db.refresh(note)
    return note


def create_test_tag(db: Session, user_id: int, name: str = "factory-tag") -> Tag:
    """创建测试标签，持久化到 DB 并返回 Tag ORM 对象。

    Args:
        db: 数据库会话。
        user_id: 所有者用户 ID。
        name: 标签名。

    Returns:
        已 commit 并 refresh 的 Tag 对象。
    """
    tag = Tag(name=name, user_id=user_id)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def create_test_share(
    db: Session,
    note_id: int,
    user_id: int,
    token: str | None = None,
    is_active: bool = True,
) -> ShareLink:
    """创建测试分享链接，持久化到 DB 并返回 ShareLink ORM 对象。

    Args:
        db: 数据库会话。
        note_id: 所属笔记 ID。
        user_id: 创建者用户 ID。
        token: 分享 token（默认自动生成 uuid4 hex）。
        is_active: 是否激活。

    Returns:
        已 commit 并 refresh 的 ShareLink 对象。
    """
    from uuid import uuid4

    share = ShareLink(
        token=token or uuid4().hex,
        note_id=note_id,
        created_by=user_id,
        is_active=is_active,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share
