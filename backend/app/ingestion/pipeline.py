from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunker import (
    ChunkingError,
    CodeChunk,
    PythonAstChunker,
)


@dataclass(frozen=True)
class ChunkingFailure:
    file_path: str
    error: str


@dataclass(frozen=True)
class IngestionResult:
    chunks: list[CodeChunk]
    failures: list[ChunkingFailure]


def chunk_extracted_files(
    files: list[Path],
    *,
    project_id: str,
    project_directory: Path,
) -> IngestionResult:
    """Chunk supported extracted source files without failing the whole project."""
    chunker = PythonAstChunker()
    chunks: list[CodeChunk] = []
    failures: list[ChunkingFailure] = []

    root = project_directory.resolve()

    for path in files:
        if path.suffix.lower() != ".py":
            continue

        relative_path = path.resolve().relative_to(root).as_posix()

        try:
            source = path.read_text(encoding="utf-8")
            chunks.extend(
                chunker.chunk(
                    source,
                    project_id=project_id,
                    file_path=relative_path,
                )
            )
        except (OSError, UnicodeDecodeError, ChunkingError) as error:
            failures.append(
                ChunkingFailure(
                    file_path=relative_path,
                    error=str(error),
                )
            )

    return IngestionResult(chunks=chunks, failures=failures)
