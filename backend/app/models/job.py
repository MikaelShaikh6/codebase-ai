from datetime import datetime, timezone
from enum import StrEnum

from sqlmodel import Field, SQLModel


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectJob(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    status: JobStatus = Field(default=JobStatus.QUEUED, index=True)
    attempts: int = Field(default=0)
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
