import asyncio
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import HTTPException, UploadFile

from app.ingestion.zip_handler import (
    MAX_EXTRACTED_SIZE,
    process_zip_upload,
    safe_extract,
)


def make_zip(files: dict[str, str | bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return buffer.getvalue()


def upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))



def test_safe_extract_filters_ignored_and_unsupported_files(tmp_path: Path) -> None:
    archive = ZipFile(
        BytesIO(
            make_zip(
                {
                    "src/main.py": "print('hello')",
                    "README.md": "# docs",
                    "node_modules/ignored.js": "ignored",
                    "image.png": "ignored",
                }
            )
        )
    )

    extracted = safe_extract(archive, tmp_path)

    assert {path.relative_to(tmp_path) for path in extracted} == {
        Path("src/main.py"),
        Path("README.md"),
    }
    assert (tmp_path / "src/main.py").read_text() == "print('hello')"
    assert not (tmp_path / "node_modules").exists()


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    archive = ZipFile(BytesIO(make_zip({"../outside.py": "unsafe"})))

    with pytest.raises(HTTPException, match="unsafe file path"):
        safe_extract(archive, tmp_path)

    assert not (tmp_path.parent / "outside.py").exists()


def test_process_zip_upload_rejects_non_zip(tmp_path: Path) -> None:
    with pytest.raises(HTTPException, match="Only ZIP files"):
        asyncio.run(process_zip_upload(upload("project.tar", b"not a zip"), tmp_path))


def test_process_zip_upload_rejects_invalid_zip(tmp_path: Path) -> None:
    with pytest.raises(HTTPException, match="valid ZIP archive"):
        asyncio.run(process_zip_upload(upload("project.zip", b"not a zip"), tmp_path))


def test_process_zip_upload_removes_temporary_archive(tmp_path: Path) -> None:
    asyncio.run(
        process_zip_upload(
            upload("project.zip", make_zip({"main.py": "print(1)"})),
            tmp_path,
        )
    )

    assert not (tmp_path / "upload.zip").exists()
    assert (tmp_path / "main.py").exists()


def test_safe_extract_rejects_extracted_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.ingestion.zip_handler.MAX_EXTRACTED_SIZE",
        3,
    )
    archive = ZipFile(BytesIO(make_zip({"main.py": "1234"})))

    with pytest.raises(HTTPException, match="too large"):
        safe_extract(archive, tmp_path)


def test_extracted_size_limit_is_configured() -> None:
    assert MAX_EXTRACTED_SIZE > 0
