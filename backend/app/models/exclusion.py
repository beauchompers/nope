from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ExclusionType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    CIDR = "cidr"
    WILDCARD = "wildcard"


class Exclusion(Base):
    __tablename__ = "exclusions"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    type: Mapped[ExclusionType] = mapped_column(
        PgEnum('ip', 'domain', 'cidr', 'wildcard', name='exclusiontype', create_type=False),
        nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
