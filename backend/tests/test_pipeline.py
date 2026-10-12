import asyncio
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi import UploadFile

from app.ingestion.pipeline import chunk_extracted_files
from app.ingestion.zip_handler import process_zip_upload


def make_zip(files: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return buffer.getvalue()


def test_zip_to_chunk_pipeline_processes_valid_python_files(tmp_path: Path) -> None:
    project_id = "project-123"
    project_directory = tmp_path / project_id
    upload = UploadFile(
        filename="project.zip",
        file=BytesIO(
            make_zip(
                {
                    "src/main.py": "def main():\n    return True\n",
                    "README.md": "# Project",
                    "node_modules/dependency.py": "def ignored():\n    pass\n",
                }
            )
        ),
    )

    extracted = asyncio.run(process_zip_upload(upload, project_directory))
    result = chunk_extracted_files(
        extracted,
        project_id=project_id,
        project_directory=project_directory,
    )

    assert len(result.chunks) == 1
    assert result.chunks[0].file_path == "src/main.py"
    assert result.chunks[0].chunk_type == "function"
    assert result.failures == []


def test_pipeline_reports_bad_python_and_processes_good_python(
    tmp_path: Path,
) -> None:
    project_directory = tmp_path / "project"
    good_file = project_directory / "good.py"
    bad_file = project_directory / "bad.py"
    good_file.parent.mkdir(parents=True)
    good_file.write_text("VALUE = 1\n", encoding="utf-8")
    bad_file.write_text("def broken(:\n", encoding="utf-8")

    result = chunk_extracted_files(
        [bad_file, good_file],
        project_id="project-123",
        project_directory=project_directory,
    )

    assert [chunk.file_path for chunk in result.chunks] == ["good.py"]
    assert result.failures[0].file_path == "bad.py"
    assert "Could not parse Python file" in result.failures[0].error


def test_pipeline_ignores_non_python_files(tmp_path: Path) -> None:
    project_directory = tmp_path / "project"
    markdown_file = project_directory / "README.md"
    markdown_file.parent.mkdir(parents=True)
    markdown_file.write_text("# docs", encoding="utf-8")

    result = chunk_extracted_files(
        [markdown_file],
        project_id="project-123",
        project_directory=project_directory,
    )

    assert result.chunks == []
    assert result.failures == []
