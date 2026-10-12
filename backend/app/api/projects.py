from pathlib import Path
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi import BackgroundTasks
from fastapi import Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import engine
from app.core.auth import get_current_user
from app.core.rate_limit import rate_limit
from app.generation.service import (
    AnswerGenerationService,
    GeneratedAnswer,
    GenerationError,
    OllamaGenerator,
    OpenAICompatibleGenerator,
)
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.ingestion.zip_handler import validate_upload_content, validate_upload_filename
from app.retrieval.service import RetrievalService
from app.services.embeddings import EmbeddingService, FastEmbedProvider
from app.services.vector_store import QdrantVectorStore, VectorStoreError
from app.models.job import ProjectJob
from app.services.storage import get_project_storage
from app.services.project_processor import process_project


router = APIRouter(prefix="/projects", tags=["projects"])


UPLOAD_DIRECTORY = Path("data/projects").resolve()


class ProjectUploadResponse(BaseModel):
    project_id: str
    filename: str
    files_found: int
    files: list[str]
    status: ProjectStatus


class ProjectResponse(BaseModel):
    project_id: str
    filename: str
    status: ProjectStatus
    files_found: int
    error: str | None
    created_at: str
    updated_at: str


class ChatRequest(BaseModel):
    question: str
    limit: int = 5


class CitationResponse(BaseModel):
    file_path: str
    start_line: int
    end_line: int


class ChatResponse(BaseModel):
    project_id: str
    question: str
    answer: str
    citations: list[CitationResponse]


def project_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.id,
        filename=project.filename,
        status=project.status,
        files_found=project.files_found,
        error=project.error,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


def get_retrieval_service() -> RetrievalService:
    return RetrievalService(
        EmbeddingService(FastEmbedProvider()),
        QdrantVectorStore(),
    )


def get_generation_service() -> AnswerGenerationService:
    if os.getenv("LLM_PROVIDER", "ollama").lower() == "openai_compatible":
        return AnswerGenerationService(OpenAICompatibleGenerator())
    return AnswerGenerationService(OllamaGenerator())


@router.get("", response_model=list[ProjectResponse])
def list_projects(current_user: User | None = Depends(get_current_user)) -> list[ProjectResponse]:
    with Session(engine) as session:
        query = select(Project).order_by(Project.created_at.desc())
        if current_user is not None:
            query = query.where(Project.owner_id == current_user.id)
        projects = session.exec(query).all()
    return [project_response(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, current_user: User | None = Depends(get_current_user)) -> ProjectResponse:
    with Session(engine) as session:
        project = session.get(Project, project_id)
    if project is None or (current_user is not None and project.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Project not found.")
    return project_response(project)


@router.get("/{project_id}/status", response_model=ProjectResponse)
def get_project_status(project_id: str, current_user: User | None = Depends(get_current_user)) -> ProjectResponse:
    return get_project(project_id, current_user)


@router.post(
    "/{project_id}/chat",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limit("chat", max_requests=20, window_seconds=3600))],
)
def chat_with_project(
    project_id: str,
    request: ChatRequest,
    current_user: User | None = Depends(get_current_user),
) -> ChatResponse:
    if request.limit < 1 or request.limit > 20:
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 20.",
        )

    with Session(engine) as session:
        project = session.get(Project, project_id)
    if project is None or (current_user is not None and project.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Project not found.")
    if project.status != ProjectStatus.READY:
        raise HTTPException(
            status_code=409,
            detail=f"Project is not ready for chat (status: {project.status}).",
        )

    try:
        chunks = get_retrieval_service().search(
            request.question,
            project_id=project_id,
            limit=request.limit,
        )
        generated: GeneratedAnswer = get_generation_service().answer(
            request.question,
            chunks,
        )
    except (GenerationError, VectorStoreError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return ChatResponse(
        project_id=project_id,
        question=request.question,
        answer=generated.answer,
        citations=[
            CitationResponse(
                file_path=citation.file_path,
                start_line=citation.start_line,
                end_line=citation.end_line,
            )
            for citation in generated.citations
        ],
    )


@router.post(
    "/upload",
    dependencies=[Depends(rate_limit("upload", max_requests=5, window_seconds=3600))],
)
async def upload_project(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    current_user: User | None = Depends(get_current_user),
) -> ProjectUploadResponse:
    project_id = str(uuid4())
    filename = file.filename

    validate_upload_filename(filename)
    content = await file.read()
    validate_upload_content(content)

    project_directory = UPLOAD_DIRECTORY / project_id
    get_project_storage().save_archive(project_id, content)

    project = Project(
        id=project_id,
        owner_id=current_user.id if isinstance(current_user, User) else None,
        filename=filename,
        status=ProjectStatus.PROCESSING,
    )

    with Session(engine) as session:
        session.add(project)
        session.add(ProjectJob(id=str(uuid4()), project_id=project_id))
        session.commit()

    # Keep local request-based processing available while the durable worker is
    # disabled; the persisted job remains available for worker recovery.
    if os.getenv("RUN_PROJECT_WORKER", "false").lower() != "true":
        background_tasks.add_task(
            process_project,
            project_id,
            project_directory=project_directory,
        )

    return ProjectUploadResponse(
        project_id=project_id,
        filename=filename,
        files_found=0,
        files=[],
        status=ProjectStatus.PROCESSING,
    )
