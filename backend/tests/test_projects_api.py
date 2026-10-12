import asyncio
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi import UploadFile
from sqlmodel import Session, SQLModel, create_engine, select

from app.api import projects
from app.models.project import Project, ProjectStatus


def zip_bytes() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("main.py", "VALUE = 1\n")
    return buffer.getvalue()


def test_upload_persists_ready_project(
    tmp_path: Path, monkeypatch
) -> None:
    database_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(database_engine)
    monkeypatch.setattr(projects, "engine", database_engine)
    monkeypatch.setattr(projects, "UPLOAD_DIRECTORY", tmp_path)

    response = asyncio.run(
        projects.upload_project(
            UploadFile(filename="project.zip", file=BytesIO(zip_bytes()))
        )
    )

    with Session(database_engine) as session:
        project = session.exec(
            select(Project).where(Project.id == response.project_id)
        ).one()

    assert response.status == ProjectStatus.READY
    assert project.status == ProjectStatus.READY
    assert project.files_found == 1
