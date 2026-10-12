from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from app.ingestion.zip_handler import process_zip_upload


router = APIRouter(prefix="/projects", tags=["projects"])


UPLOAD_DIRECTORY = Path("data/projects").resolve()


class ProjectUploadResponse(BaseModel):
    project_id: str
    filename: str
    files_found: int
    files: list[str]


@router.post("/upload")
async def upload_project(file: UploadFile) -> ProjectUploadResponse:
    project_id = str(uuid4())

    project_directory = UPLOAD_DIRECTORY / project_id

    extracted_files = await process_zip_upload(
        file=file,
        destination=project_directory,
    )

    return ProjectUploadResponse(
        project_id=project_id,
        filename=file.filename,
        files_found=len(extracted_files),
        files=[
            str(path.relative_to(project_directory))
            for path in extracted_files
        ],
    )
