from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api import projects
from app.generation.service import AnswerGenerationService
from app.main import app
from app.models.project import Project, ProjectStatus
from app.retrieval.service import RetrievedChunk


def client_with_database(monkeypatch):
    database_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(database_engine)
    monkeypatch.setattr(projects, "engine", database_engine)
    return TestClient(app), database_engine


def add_project(engine, status: ProjectStatus = ProjectStatus.READY) -> None:
    with Session(engine) as session:
        session.add(
            Project(
                id="project-1",
                filename="project.zip",
                status=status,
                files_found=2,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def test_project_status_endpoint_returns_project(
    monkeypatch,
) -> None:
    client, database_engine = client_with_database(monkeypatch)
    add_project(database_engine)

    response = client.get("/projects/project-1/status")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_project_status_endpoint_returns_not_found(monkeypatch) -> None:
    client, _ = client_with_database(monkeypatch)

    response = client.get("/projects/missing/status")

    assert response.status_code == 404


def test_chat_endpoint_returns_answer_and_citations(monkeypatch) -> None:
    client, database_engine = client_with_database(monkeypatch)
    add_project(database_engine)

    class FakeRetrieval:
        def search(self, question: str, *, project_id: str, limit: int):
            return [
                RetrievedChunk(
                    score=0.9,
                    project_id=project_id,
                    file_path="src/auth.py",
                    start_line=4,
                    end_line=8,
                    chunk_type="function",
                    language="python",
                    content="def authenticate(): pass",
                )
            ]

    class FakeGeneration:
        def answer(self, question, chunks):
            return AnswerGenerationService(
                type("Generator", (), {"generate": lambda _, prompt: "Auth works here."})()
            ).answer(question, chunks)

    monkeypatch.setattr(projects, "get_retrieval_service", lambda: FakeRetrieval())
    monkeypatch.setattr(projects, "get_generation_service", lambda: FakeGeneration())

    response = client.post(
        "/projects/project-1/chat",
        json={"question": "How does auth work?", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Auth works here."
    assert response.json()["citations"] == [
        {"file_path": "src/auth.py", "start_line": 4, "end_line": 8}
    ]


def test_chat_rejects_project_that_is_not_ready(monkeypatch) -> None:
    client, database_engine = client_with_database(monkeypatch)
    add_project(database_engine, ProjectStatus.PROCESSING)

    response = client.post(
        "/projects/project-1/chat",
        json={"question": "How does auth work?"},
    )

    assert response.status_code == 409
