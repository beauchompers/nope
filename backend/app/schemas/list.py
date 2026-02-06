from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ListType = Literal["ip", "domain", "hash", "mixed"]


class ListCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    list_type: ListType = "mixed"


class ListUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    list_type: ListType | None = None


class ListResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    tags: list[str] | None
    list_type: ListType
    ioc_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ListSummary(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    tags: list[str] | None
    list_type: ListType
    ioc_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
