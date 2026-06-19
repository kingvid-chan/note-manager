"""笔记模型 — 核心业务实体。"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String, Text, Boolean, DateTime, ForeignKey, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(
        String(256), nullable=False, default="Untitled"
    )
    content_md: Mapped[str] = mapped_column(Text, default="")
    content_html: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    author: Mapped["User"] = relationship(back_populates="notes")
    tags: Mapped[List["Tag"]] = relationship(
        secondary="note_tags", back_populates="notes"
    )
    share_links: Mapped[List["ShareLink"]] = relationship(back_populates="note")

    # 联合索引 — 按用户 + 时间排序分页
    __table_args__ = (
        Index("ix_notes_user_created", "user_id", "created_at"),
    )
