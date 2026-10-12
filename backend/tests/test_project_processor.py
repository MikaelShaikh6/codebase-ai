from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from qdrant_client import QdrantClient
from sqlmodel import Session, SQLModel, create_engine

from app.ingestion.chunker import CodeChunk
from app.models.project import Project, ProjectStatus
from app.services.embeddings import EmbeddedChunk, EmbeddingService
from app.services.project_processor import process_project
from app.services.vector_store import QdrantVectorStore


class FakeProvider:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_processor_indexes_project_and_marks_ready(
    tmp_path: Path, monkeypatch
) -> None:
    database_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(database_engine)
    monkeypatch.setattr("app.services.project_processor.engine", database_engine)
    with Session(database_engine) as session:
        session.add(Project(id="project-1", filename="project.zip",
                            status=ProjectStatus.PROCESSING))
        session.commit()

    project_directory = tmp_path / "project-1"
    project_directory.mkdir()
    archive_path = project_directory / "upload.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("main.py", "def main():\n    return True\n")

    store = QdrantVectorStore(
        QdrantClient(":memory:"),
        collection_name="processor_test",
    )
    process_project(
        "project-1",
        project_directory=project_directory,
        embedding_service=EmbeddingService(FakeProvider()),
        vector_store=store,
    )

    with Session(database_engine) as session:
        project = session.get(Project, "project-1")

    assert project is not None
    assert project.status == ProjectStatus.READY
    assert project.files_found == 1
    assert not archive_path.exists()
    assert store.client.count("processor_test").count == 1


def test_processor_marks_failed_when_archive_is_invalid(
    tmp_path: Path, monkeypatch
) -> None:
    database_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(database_engine)
    monkeypatch.setattr("app.services.project_processor.engine", database_engine)
    with Session(database_engine) as session:
        session.add(Project(id="project-1", filename="project.zip",
                            status=ProjectStatus.PROCESSING))
        session.commit()

    project_directory = tmp_path / "project-1"
    project_directory.mkdir()
    (project_directory / "upload.zip").write_bytes(b"invalid")

    process_project("project-1", project_directory=project_directory)

    with Session(database_engine) as session:
        project = session.get(Project, "project-1")

    assert project is not None
    assert project.status == ProjectStatus.FAILED
    assert "valid ZIP" in (project.error or "")
