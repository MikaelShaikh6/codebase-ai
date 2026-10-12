from pathlib import Path
from zipfile import ZipFile, BadZipFile

from fastapi import HTTPException, UploadFile


SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".go",
    ".rs",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".html",
    ".css",
    ".sql",
    ".example",
}

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
}

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_EXTRACTED_SIZE = 200 * 1024 * 1024  # 200 MB


def is_supported_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def is_ignored_path(path: Path) -> bool:
    return any(part in IGNORED_DIRECTORIES for part in path.parts)


def safe_extract(zip_file: ZipFile, destination: Path) -> list[Path]:
    extracted_files = []
    total_size = 0

    destination = destination.resolve()

    for member in zip_file.infolist():
        member_path = Path(member.filename)

        # Ignore directories.
        if member.is_dir():
            continue

        # Prevent path traversal.
        target_path = (destination / member_path).resolve()

        if target_path != destination and destination not in target_path.parents:
            raise HTTPException(
                status_code=400,
                detail="ZIP contains an unsafe file path.",
            )

        # Ignore unwanted directories/files.
        if is_ignored_path(member_path):
            continue

        # Ignore unsupported files.
        if not is_supported_file(member_path):
            continue

        total_size += member.file_size

        if total_size > MAX_EXTRACTED_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Extracted project is too large.",
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)

        with zip_file.open(member) as source, open(target_path, "wb") as target:
            target.write(source.read())

        extracted_files.append(target_path)

    return extracted_files


async def process_zip_upload(
    file: UploadFile,
    destination: Path,
) -> list[Path]:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A file is required.",
        )

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only ZIP files are supported.",
        )

    content = await file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="ZIP file is too large. Maximum size is 50 MB.",
        )

    destination.mkdir(parents=True, exist_ok=True)

    zip_path = destination / "upload.zip"

    try:
        zip_path.write_bytes(content)

        with ZipFile(zip_path) as zip_file:
            return safe_extract(zip_file, destination)

    except BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid ZIP archive.",
        )
    finally:
        if zip_path.exists():
            zip_path.unlink()
