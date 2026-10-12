from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import engine
from app.models.project import Project, ProjectStatus
from app.ingestion.zip_handler import process_zip_upload


router = APIRouter(prefix="/projects", tags=["projects"])


UPLOAD_DIRECTORY = Path("data/projects").resolve()


class ProjectUploadResponse(BaseModel):
    project_id: str
    filename: str
    files_found: int
    files: list[str]
    status: ProjectStatus


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
