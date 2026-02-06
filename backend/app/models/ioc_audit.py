from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class IOCAuditAction(str, Enum):
    CREATED = "created"
    ADDED_TO_LIST = "added_to_list"
    REMOVED_FROM_LIST = "removed_from_list"
    COMMENT = "comment"
    DELETED = "deleted"


class IOCAuditLog(Base):
    __tablename__ = "ioc_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ioc_id: Mapped[int] = mapped_column(Integer, ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    list_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("lists.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    ioc: Mapped["IOC"] = relationship(back_populates="audit_logs")
    list: Mapped["List | None"] = relationship()
