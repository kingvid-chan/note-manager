"""活动日志模型 — 关键操作审计追踪。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, DateTime, ForeignKey, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    target_type: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    target_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), index=True
    )
