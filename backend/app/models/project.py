from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ProjectStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Project(SQLModel, table=True):
    id: str = Field(primary_key=True)
    filename: str
    status: ProjectStatus = Field(default=ProjectStatus.UPLOADED)
    files_found: int = Field(default=0)
    error: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
