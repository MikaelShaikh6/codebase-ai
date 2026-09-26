from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile

from app.ingestion.zip_handler import process_zip_upload


router = APIRouter(prefix="/projects", tags=["projects"])


UPLOAD_DIRECTORY = Path("data/projects").resolve()


@router.post("/upload")
async def upload_project(file: UploadFile):
    project_id = str(uuid4())

    project_directory = UPLOAD_DIRECTORY / project_id

    extracted_files = await process_zip_upload(
        file=file,
        destination=project_directory,
    )

    return {
        "project_id": project_id,
        "filename": file.filename,
        "files_found": len(extracted_files),
        "files": [
            str(path.relative_to(project_directory))
            for path in extracted_files
        ],
    }
