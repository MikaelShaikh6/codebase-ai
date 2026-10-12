from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import engine
from app.generation.service import (
    AnswerGenerationService,
    GeneratedAnswer,
    GenerationError,
    OllamaGenerator,
)
from app.models.project import Project, ProjectStatus
from app.ingestion.zip_handler import process_zip_upload
from app.retrieval.service import RetrievalService
from app.services.embeddings import EmbeddingService, FastEmbedProvider
from app.services.vector_store import QdrantVectorStore, VectorStoreError


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
    return AnswerGenerationService(OllamaGenerator())


@router.get("", response_model=list[ProjectResponse])
def list_projects() -> list[ProjectResponse]:
    with Session(engine) as session:
        projects = session.exec(
            select(Project).order_by(Project.created_at.desc())
        ).all()
    return [project_response(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str) -> ProjectResponse:
    with Session(engine) as session:
        project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project_response(project)


@router.get("/{project_id}/status", response_model=ProjectResponse)
def get_project_status(project_id: str) -> ProjectResponse:
    return get_project(project_id)


@router.post("/{project_id}/chat", response_model=ChatResponse)
def chat_with_project(
    project_id: str,
    request: ChatRequest,
) -> ChatResponse:
    if request.limit < 1 or request.limit > 20:
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 20.",
        )

    with Session(engine) as session:
        project = session.get(Project, project_id)
    if project is None:
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


@router.post("/upload")
async def upload_project(file: UploadFile) -> ProjectUploadResponse:
    project_id = str(uuid4())
    filename = file.filename

    if not filename:
        raise HTTPException(status_code=400, detail="A file is required.")

    project_directory = UPLOAD_DIRECTORY / project_id

    project = Project(
        id=project_id,
        filename=filename,
        status=ProjectStatus.PROCESSING,
    )

    with Session(engine) as session:
        session.add(project)
        session.commit()

    try:
        extracted_files = await process_zip_upload(
            file=file,
            destination=project_directory,
        )
    except (HTTPException, OSError) as error:
        with Session(engine) as session:
            failed_project = session.get(Project, project_id)
            if failed_project:
                failed_project.status = ProjectStatus.FAILED
                failed_project.error = str(error)
                session.add(failed_project)
                session.commit()
        raise

    with Session(engine) as session:
        saved_project = session.get(Project, project_id)
        if saved_project:
            saved_project.status = ProjectStatus.READY
            saved_project.files_found = len(extracted_files)
            session.add(saved_project)
            session.commit()

    return ProjectUploadResponse(
        project_id=project_id,
        filename=filename,
        files_found=len(extracted_files),
        files=[
            str(path.relative_to(project_directory))
            for path in extracted_files
        ],
        status=ProjectStatus.READY,
    )
