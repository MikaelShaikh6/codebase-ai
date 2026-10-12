from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.core.database import engine
from app.ingestion.pipeline import chunk_extracted_files
from app.ingestion.zip_handler import extract_zip_file
from app.models.project import Project, ProjectStatus
from app.services.embeddings import EmbeddingService, FastEmbedProvider
from app.services.vector_store import QdrantVectorStore
from app.services.storage import get_project_storage


def process_project(
    project_id: str,
    *,
    project_directory: Path,
    embedding_service: EmbeddingService | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> None:
    archive_path = project_directory / "upload.zip"

    try:
        if not archive_path.exists():
            get_project_storage().restore_archive(project_id, project_directory)
        extracted_files = extract_zip_file(archive_path, project_directory)
        ingestion = chunk_extracted_files(
            extracted_files,
            project_id=project_id,
            project_directory=project_directory,
        )

        if ingestion.chunks:
            embedder = embedding_service or EmbeddingService(FastEmbedProvider())
            store = vector_store or QdrantVectorStore()
            store.index_chunks(embedder.embed_chunks(ingestion.chunks))

        error = "; ".join(
            f"{failure.file_path}: {failure.error}"
            for failure in ingestion.failures
        ) or None
        _update_project(
            project_id,
            status=ProjectStatus.READY,
            files_found=len(extracted_files),
            error=error,
        )
    except Exception as error:
        _update_project(
            project_id,
            status=ProjectStatus.FAILED,
            error=str(error),
        )
    finally:
        if archive_path.exists():
            archive_path.unlink()


def _update_project(
    project_id: str,
    *,
    status: ProjectStatus,
    files_found: int | None = None,
    error: str | None = None,
) -> None:
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            return
        project.status = status
        project.error = error
        if files_found is not None:
            project.files_found = files_found
        session.add(project)
        session.commit()
