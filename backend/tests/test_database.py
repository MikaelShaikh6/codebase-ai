from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from app.core import database


def test_existing_project_table_gets_owner_id_column(monkeypatch) -> None:
    legacy_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE project (
                id VARCHAR NOT NULL PRIMARY KEY,
                filename VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                files_found INTEGER NOT NULL,
                error VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )

    monkeypatch.setattr(database, "engine", legacy_engine)
    database.create_db_and_tables()

    columns = {
        column["name"]
        for column in inspect(legacy_engine).get_columns("project")
    }
    assert "owner_id" in columns
