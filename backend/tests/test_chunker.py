from pathlib import Path

import pytest

from app.ingestion.chunker import (
    ChunkingError,
    PythonAstChunker,
    chunk_python_file,
)


def test_python_chunker_creates_module_functions_async_functions_and_classes() -> None:
    source = """import os

VALUE = 1

def greet(name):
    return f"Hello {name}"

async def load():
    return VALUE

class Service:
    def run(self):
        return greet("world")
"""

    chunks = PythonAstChunker().chunk(
        source,
        project_id="project-1",
        file_path="src/service.py",
    )

    assert [chunk.chunk_type for chunk in chunks] == [
        "module",
        "function",
        "async_function",
        "class",
    ]
    assert chunks[0].content == "import os\nVALUE = 1"
    assert chunks[1].start_line == 5
    assert chunks[1].end_line == 6
    assert chunks[2].start_line == 8
    assert chunks[2].end_line == 9
    assert chunks[3].start_line == 11
    assert chunks[3].end_line == 13


def test_decorated_function_chunk_includes_decorator() -> None:
    source = """@staticmethod
def build():
    return True
"""

    chunk = PythonAstChunker().chunk(
        source,
        project_id="project-1",
        file_path="service.py",
    )[0]

    assert chunk.chunk_type == "function"
    assert chunk.start_line == 1
    assert chunk.end_line == 3
    assert chunk.content.startswith("@staticmethod")


def test_chunks_have_stable_ids_and_metadata() -> None:
    kwargs = {
        "project_id": "project-1",
        "file_path": "main.py",
    }
    first = PythonAstChunker().chunk("print('hello')\n", **kwargs)[0]
    second = PythonAstChunker().chunk("print('hello')\n", **kwargs)[0]

    assert first == second
    assert len(first.chunk_id) == 64
    assert first.language == "python"
    assert first.project_id == "project-1"


def test_chunk_python_file_uses_path_metadata(tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("VALUE = 42\n", encoding="utf-8")

    chunk = chunk_python_file(path, project_id="project-1")[0]

    assert chunk.file_path == path.as_posix()
    assert chunk.content == "VALUE = 42"


def test_python_chunker_reports_syntax_errors() -> None:
    with pytest.raises(ChunkingError, match="Could not parse Python file"):
        PythonAstChunker().chunk(
            "def broken(:\n    pass\n",
            project_id="project-1",
            file_path="broken.py",
        )


def test_python_chunker_returns_no_chunks_for_empty_file() -> None:
    assert PythonAstChunker().chunk(
        "",
        project_id="project-1",
        file_path="empty.py",
    ) == []
