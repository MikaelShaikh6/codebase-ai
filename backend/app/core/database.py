from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DATABASE_URL = "sqlite:///data/codebase.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith(
    "sqlite:///:memory:"
):
    database_path = Path(DATABASE_URL.removeprefix("sqlite:///"))
    database_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_existing_schema()


def _migrate_existing_schema() -> None:
    inspector = inspect(engine)
    project_columns = {
        column["name"] for column in inspector.get_columns("project")
    }
    if "owner_id" not in project_columns:
        with engine.begin() as connection:
            if engine.dialect.name == "sqlite":
                connection.execute(
                    text("ALTER TABLE project ADD COLUMN owner_id VARCHAR")
                )
            elif engine.dialect.name == "postgresql":
                connection.execute(
                    text(
                        "ALTER TABLE project ADD COLUMN IF NOT EXISTS "
                        "owner_id VARCHAR"
                    )
                )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
