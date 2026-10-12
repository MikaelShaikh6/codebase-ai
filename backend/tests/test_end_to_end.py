from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import main
from app.api import projects
from app.generation.service import AnswerGenerationService
from app.models.project import Project, ProjectStatus
from app.retrieval.service import RetrievalService
from app.services.embeddings import EmbeddingService
from app.services import project_processor
from app.services.project_processor import process_project
from app.services.vector_store import QdrantVectorStore


class FakeEmbeddingProvider:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeGenerator:
    def generate(self, prompt: str) -> str:
        return "The entry point is defined in the uploaded project."


def project_zip() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "src/main.py",
            "def main():\n    return True\n",
        )
    return buffer.getvalue()


def test_upload_to_ready_to_chat_flow(monkeypatch, tmp_path: Path) -> None:
    database_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(database_engine)
    monkeypatch.setattr(projects, "engine", database_engine)
    monkeypatch.setattr(project_processor, "engine", database_engine)
    monkeypatch.setattr(main, "create_db_and_tables", lambda: None)

    vector_store = QdrantVectorStore(
        QdrantClient(":memory:"),
        collection_name="e2e_chunks",
    )
    embedding_service = EmbeddingService(FakeEmbeddingProvider())

    def process_in_background(
        project_id: str,
        *,
        project_directory: Path,
    ) -> None:
        process_project(
            project_id,
            project_directory=project_directory,
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

    monkeypatch.setattr(projects, "process_project", process_in_background)
    monkeypatch.setattr(projects, "UPLOAD_DIRECTORY", tmp_path)

    def retrieval_service() -> RetrievalService:
        return RetrievalService(embedding_service, vector_store)

    monkeypatch.setattr(projects, "get_retrieval_service", retrieval_service)
    monkeypatch.setattr(
        projects,
        "get_generation_service",
        lambda: AnswerGenerationService(FakeGenerator()),
    )

    with TestClient(main.app) as client:
        upload_response = client.post(
            "/projects/upload",
            files={"file": ("project.zip", project_zip(), "application/zip")},
        )

        assert upload_response.status_code == 200
        upload = upload_response.json()
        assert upload["status"] == "processing"
        project_id = upload["project_id"]

        status_response = client.get(f"/projects/{project_id}/status")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "ready"
        assert status_response.json()["files_found"] == 1

        chat_response = client.post(
            f"/projects/{project_id}/chat",
            json={"question": "Where is the entry point?"},
        )

    assert chat_response.status_code == 200
    assert chat_response.json()["answer"] == (
        "The entry point is defined in the uploaded project."
    )
    assert chat_response.json()["citations"] == [
        {"file_path": "src/main.py", "start_line": 1, "end_line": 2}
    ]

    with Session(database_engine) as session:
        project = session.get(Project, project_id)

    assert project is not None
    assert project.status == ProjectStatus.READY
