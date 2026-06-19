"""模型单元测试 — User / Note / Tag / ShareLink。

验证唯一约束、外键完整性、级联删除和复合主键。
每个测试函数通过 ``db`` fixture 获得完全隔离的内存 SQLite 数据库。
"""

import pytest
from sqlalchemy import inspect, delete
from sqlalchemy.exc import IntegrityError

from src.note_manager.models import User, Note, Tag, NoteTag, ShareLink, ActivityLog
from src.note_manager.services.auth_service import hash_password


# ═════════════════════════════════════════════════════════════════
# User 模型
# ═════════════════════════════════════════════════════════════════

class TestUserModel:
    """User 模型 — 字段、约束、默认值。"""

    def test_create_user(self, db):
        """基本创建 — 所有字段应正确持久化。"""
        user = User(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("secret"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.is_active is True
        assert user.is_demo is False
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_username_unique_constraint(self, db):
        """重复 username → IntegrityError。"""
        db.add(User(username="bob", email="bob@example.com", password_hash="hash1"))
        db.commit()

        db.add(User(username="bob", email="bob2@example.com", password_hash="hash2"))
        with pytest.raises(IntegrityError):
            db.commit()

    def test_email_unique_constraint(self, db):
        """重复 email → IntegrityError。"""
        db.add(User(username="carol", email="carol@example.com", password_hash="hash1"))
        db.commit()

        db.add(User(username="carol2", email="carol@example.com", password_hash="hash2"))
        with pytest.raises(IntegrityError):
            db.commit()

    def test_username_max_length(self, db):
        """username 列应为 String(64)。"""
        mapper = inspect(User)
        col = mapper.columns["username"]
        assert col.type.length == 64

    def test_email_max_length(self, db):
        """email 列应为 String(255)。"""
        mapper = inspect(User)
        col = mapper.columns["email"]
        assert col.type.length == 255


# ═════════════════════════════════════════════════════════════════
# Note 模型
# ═════════════════════════════════════════════════════════════════

class TestNoteModel:
    """Note 模型 — FK、默认值、级联删除。"""

    def test_create_note(self, db, test_user):
        """基本创建 — FK 指向 User，默认值正确。"""
        note = Note(title="My Note", content_md="# Hello", user_id=test_user.id)
        db.add(note)
        db.commit()
        db.refresh(note)

        assert note.id is not None
        assert note.title == "My Note"
        assert note.content_md == "# Hello"
        assert note.user_id == test_user.id
        assert note.is_published is False
        assert note.created_at is not None
        assert note.updated_at is not None

    def test_default_title(self, db, test_user):
        """不传 title 时默认 "Untitled"。"""
        note = Note(user_id=test_user.id)
        db.add(note)
        db.commit()
        db.refresh(note)
        assert note.title == "Untitled"

    def test_default_content(self, db, test_user):
        """不传 content_md 时默认为空字符串。"""
        note = Note(user_id=test_user.id)
        db.add(note)
        db.commit()
        db.refresh(note)
        assert note.content_md == ""

    def test_foreign_key_invalid_user(self, db):
        """FK 指向不存在的 user_id → IntegrityError。"""
        note = Note(title="Orphan", user_id=99999)
        db.add(note)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_cascade_delete_user_deletes_notes(self, db, test_user):
        """删除 User → CASCADE 删除其所有 Note。

        使用 bulk delete 绕过 ORM 层直接测试 DB 级联。
        """
        note = Note(title="Will be deleted", user_id=test_user.id)
        db.add(note)
        db.commit()
        note_id = note.id
        user_id = test_user.id

        db.execute(delete(User).where(User.id == user_id))
        db.commit()

        assert db.query(Note).filter(Note.id == note_id).first() is None

    def test_title_max_length(self, db):
        """title 列应为 String(256)。"""
        mapper = inspect(Note)
        col = mapper.columns["title"]
        assert col.type.length == 256

    def test_relationship_author(self, db, test_user):
        """note.author 应正确 back_populates。"""
        note = Note(title="Rel", user_id=test_user.id)
        db.add(note)
        db.commit()
        db.refresh(note)

        assert note.author is not None
        assert note.author.id == test_user.id
        assert note in test_user.notes


# ═════════════════════════════════════════════════════════════════
# Tag 模型
# ═════════════════════════════════════════════════════════════════

class TestTagModel:
    """Tag 模型 — FK、唯一约束 (user_id, name)。"""

    def test_create_tag(self, db, test_user):
        """基本创建。"""
        tag = Tag(name="python", user_id=test_user.id)
        db.add(tag)
        db.commit()
        db.refresh(tag)

        assert tag.id is not None
        assert tag.name == "python"
        assert tag.user_id == test_user.id

    def test_unique_user_tag_name(self, db, test_user):
        """同一用户不能创建同名标签。"""
        db.add(Tag(name="python", user_id=test_user.id))
        db.commit()

        db.add(Tag(name="python", user_id=test_user.id))
        with pytest.raises(IntegrityError):
            db.commit()

    def test_different_users_same_tag_name(self, db, test_user, other_user):
        """不同用户可以创建同名标签。"""
        db.add(Tag(name="python", user_id=test_user.id))
        db.commit()

        db.add(Tag(name="python", user_id=other_user.id))
        db.commit()  # 不应抛出异常

        tags = db.query(Tag).filter(Tag.name == "python").all()
        assert len(tags) == 2

    def test_foreign_key_invalid_user(self, db):
        """FK 指向不存在的 user_id → IntegrityError。"""
        tag = Tag(name="orphan", user_id=99999)
        db.add(tag)
        with pytest.raises(IntegrityError):
            db.commit()

    def test_cascade_delete_user_deletes_tags(self, db, test_user):
        """删除 User → CASCADE 删除其所有 Tag。

        使用 bulk delete 绕过 ORM 层直接测试 DB 级联。
        """
        tag = Tag(name="todelete", user_id=test_user.id)
        db.add(tag)
        db.commit()
        tag_id = tag.id
        user_id = test_user.id

        db.execute(delete(User).where(User.id == user_id))
        db.commit()

        assert db.query(Tag).filter(Tag.id == tag_id).first() is None

    def test_relationship_owner(self, db, test_user):
        """tag.owner 应正确 back_populates。"""
        tag = Tag(name="web", user_id=test_user.id)
        db.add(tag)
        db.commit()
        db.refresh(tag)

        assert tag.owner is not None
        assert tag.owner.id == test_user.id
        assert tag in test_user.tags


# ═════════════════════════════════════════════════════════════════
# NoteTag 模型（多对多关联表）
# ═════════════════════════════════════════════════════════════════

class TestNoteTagModel:
    """NoteTag — 复合主键、FK 级联删除。"""

    def test_create_note_tag(self, db, test_user):
        """基本创建关联。"""
        note = Note(title="N", user_id=test_user.id)
        tag = Tag(name="T", user_id=test_user.id)
        db.add_all([note, tag])
        db.flush()

        nt = NoteTag(note_id=note.id, tag_id=tag.id)
        db.add(nt)
        db.commit()
        db.refresh(nt)

        assert nt.note_id == note.id
        assert nt.tag_id == tag.id
        assert nt.created_at is not None

    def test_composite_primary_key(self, db, test_user):
        """同一 (note_id, tag_id) 组合不能重复。"""
        note = Note(title="N", user_id=test_user.id)
        tag = Tag(name="T", user_id=test_user.id)
        db.add_all([note, tag])
        db.flush()

        db.add(NoteTag(note_id=note.id, tag_id=tag.id))
        db.commit()

        db.add(NoteTag(note_id=note.id, tag_id=tag.id))
        with pytest.raises(IntegrityError):
            db.commit()

    def test_cascade_delete_note_removes_notetag(self, db, test_user):
        """删除 Note → CASCADE 删除 NoteTag 关联。"""
        note = Note(title="N", user_id=test_user.id)
        tag = Tag(name="T", user_id=test_user.id)
        db.add_all([note, tag])
        db.flush()

        nt = NoteTag(note_id=note.id, tag_id=tag.id)
        db.add(nt)
        db.commit()
        nt_note_id = nt.note_id
        nt_tag_id = nt.tag_id

        db.delete(note)
        db.commit()

        result = db.query(NoteTag).filter(
            NoteTag.note_id == nt_note_id, NoteTag.tag_id == nt_tag_id
        ).first()
        assert result is None

    def test_cascade_delete_tag_removes_notetag(self, db, test_user):
        """删除 Tag → CASCADE 删除 NoteTag 关联。"""
        note = Note(title="N", user_id=test_user.id)
        tag = Tag(name="T", user_id=test_user.id)
        db.add_all([note, tag])
        db.flush()

        nt = NoteTag(note_id=note.id, tag_id=tag.id)
        db.add(nt)
        db.commit()
        nt_note_id = nt.note_id
        nt_tag_id = nt.tag_id

        db.delete(tag)
        db.commit()

        result = db.query(NoteTag).filter(
            NoteTag.note_id == nt_note_id, NoteTag.tag_id == nt_tag_id
        ).first()
        assert result is None


# ═════════════════════════════════════════════════════════════════
# ShareLink 模型
# ═════════════════════════════════════════════════════════════════

class TestShareLinkModel:
    """ShareLink 模型 — 唯一 token、FK 级联删除、默认值。"""

    def test_create_share_link(self, db, test_user):
        """基本创建。"""
        note = Note(title="Shared", user_id=test_user.id)
        db.add(note)
        db.flush()

        share = ShareLink(
            token="abc123",
            note_id=note.id,
            created_by=test_user.id,
        )
        db.add(share)
        db.commit()
        db.refresh(share)

        assert share.id is not None
        assert share.token == "abc123"
        assert share.note_id == note.id
        assert share.created_by == test_user.id
        assert share.is_active is True
        assert share.created_at is not None

    def test_token_unique_constraint(self, db, test_user):
        """重复 token → IntegrityError。"""
        note = Note(title="N", user_id=test_user.id)
        db.add(note)
        db.flush()

        db.add(ShareLink(token="dup", note_id=note.id, created_by=test_user.id))
        db.commit()

        note2 = Note(title="N2", user_id=test_user.id)
        db.add(note2)
        db.flush()

        db.add(ShareLink(token="dup", note_id=note2.id, created_by=test_user.id))
        with pytest.raises(IntegrityError):
            db.commit()

    def test_foreign_key_note_cascade(self, db, test_user):
        """删除 Note → CASCADE 删除 ShareLink。

        使用 bulk delete 绕过 ORM 层直接测试 DB 级联。
        """
        note = Note(title="N", user_id=test_user.id)
        db.add(note)
        db.flush()

        share = ShareLink(token="tok", note_id=note.id, created_by=test_user.id)
        db.add(share)
        db.commit()
        share_id = share.id
        note_id = note.id

        db.execute(delete(Note).where(Note.id == note_id))
        db.commit()

        assert db.query(ShareLink).filter(ShareLink.id == share_id).first() is None

    def test_foreign_key_user_cascade(self, db, test_user):
        """删除 User → CASCADE 删除其创建的 ShareLink。

        使用 bulk delete 绕过 ORM 层直接测试 DB 级联。
        """
        note = Note(title="N", user_id=test_user.id)
        db.add(note)
        db.flush()

        share = ShareLink(token="tok2", note_id=note.id, created_by=test_user.id)
        db.add(share)
        db.commit()
        share_id = share.id
        user_id = test_user.id

        db.execute(delete(User).where(User.id == user_id))
        db.commit()

        assert db.query(ShareLink).filter(ShareLink.id == share_id).first() is None

    def test_expires_at_nullable(self, db, test_user):
        """expires_at 可为 None（永不过期）。"""
        note = Note(title="N", user_id=test_user.id)
        db.add(note)
        db.flush()

        share = ShareLink(token="never", note_id=note.id, created_by=test_user.id)
        db.add(share)
        db.commit()
        db.refresh(share)

        assert share.expires_at is None

    def test_relationship_note(self, db, test_user):
        """share.note 应正确 back_populates。"""
        note = Note(title="N", user_id=test_user.id)
        db.add(note)
        db.flush()

        share = ShareLink(token="rel", note_id=note.id, created_by=test_user.id)
        db.add(share)
        db.commit()
        db.refresh(share)

        assert share.note is not None
        assert share.note.id == note.id
        assert share in note.share_links


# ═════════════════════════════════════════════════════════════════
# ActivityLog 模型
# ═════════════════════════════════════════════════════════════════

class TestActivityLogModel:
    """ActivityLog — FK SET NULL、字段默认值。"""

    def test_create_activity_log(self, db, test_user):
        """基本创建。"""
        log = ActivityLog(
            user_id=test_user.id,
            action="test_action",
            target_type="note",
            target_id=1,
            detail="Test detail",
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        assert log.id is not None
        assert log.action == "test_action"
        assert log.created_at is not None

    def test_set_null_on_user_delete(self, db, test_user):
        """删除 User → ActivityLog.user_id SET NULL（非 CASCADE）。"""
        log = ActivityLog(
            user_id=test_user.id,
            action="login",
        )
        db.add(log)
        db.commit()
        log_id = log.id

        db.delete(test_user)
        db.commit()

        log_after = db.query(ActivityLog).filter(ActivityLog.id == log_id).first()
        assert log_after is not None  # 行仍存在
        assert log_after.user_id is None  # FK 被设为 NULL
