import re
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db import Base


class ListType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH = "hash"
    MIXED = "mixed"


class List(Base):
    __tablename__ = "lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    list_type: Mapped[str] = mapped_column(String(10), nullable=False, default=ListType.MIXED.value)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    list_iocs: Mapped[list["ListIOC"]] = relationship(back_populates="list", cascade="all, delete-orphan")

    @validates("slug")
    def validate_slug(self, key, slug):
        if not re.match(r"^[a-z0-9]+$", slug):
            raise ValueError("Slug must be lowercase alphanumeric only")
        return slug

    @staticmethod
    def generate_slug(name: str) -> str:
        """Generate URL-safe slug from display name."""
        return re.sub(r"[^a-z0-9]", "", name.lower())
