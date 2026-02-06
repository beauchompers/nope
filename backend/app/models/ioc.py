from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class IOCType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    WILDCARD = "wildcard"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"


class IOC(Base):
    __tablename__ = "iocs"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    type: Mapped[IOCType] = mapped_column(
        PgEnum('ip', 'domain', 'wildcard', 'md5', 'sha1', 'sha256', name='ioctype', create_type=False),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    list_iocs: Mapped[list["ListIOC"]] = relationship(back_populates="ioc", cascade="all, delete-orphan")
    comments: Mapped[list["IOCComment"]] = relationship(back_populates="ioc", cascade="all, delete-orphan")
    audit_logs: Mapped[list["IOCAuditLog"]] = relationship(back_populates="ioc", cascade="all, delete-orphan")


class ListIOC(Base):
    __tablename__ = "list_iocs"
    __table_args__ = (UniqueConstraint("list_id", "ioc_id", name="uq_list_ioc"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("lists.id", ondelete="CASCADE"), nullable=False)
    ioc_id: Mapped[int] = mapped_column(ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    added_by: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    list: Mapped["List"] = relationship(back_populates="list_iocs")
    ioc: Mapped["IOC"] = relationship(back_populates="list_iocs")


class IOCComment(Base):
    __tablename__ = "ioc_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ioc_id: Mapped[int] = mapped_column(ForeignKey("iocs.id", ondelete="CASCADE"), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    ioc: Mapped["IOC"] = relationship(back_populates="comments")
