"""标签模型 — 用户级分类，与笔记多对多关联。"""

from datetime import datetime
from typing import List

from sqlalchemy import (
    String, DateTime, ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 关系
    owner: Mapped["User"] = relationship(back_populates="tags")
    notes: Mapped[List["Note"]] = relationship(
        secondary="note_tags", back_populates="tags"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
    )


class NoteTag(Base):
    """笔记-标签多对多关联表。"""

    __tablename__ = "note_tags"

    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
