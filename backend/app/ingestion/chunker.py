from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ChunkingError(ValueError):
    """Raised when a source file cannot be parsed into chunks."""


@dataclass(frozen=True)
class CodeChunk:
    project_id: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str
    chunk_id: str
    language: str
    content: str


class SourceChunker(Protocol):
    def chunk(
        self,
        source: str,
        *,
        project_id: str,
        file_path: str,
    ) -> list[CodeChunk]:
        ...


class PythonAstChunker:
    language = "python"

    def chunk(
        self,
        source: str,
        *,
        project_id: str,
        file_path: str,
    ) -> list[CodeChunk]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as error:
            raise ChunkingError(
                f"Could not parse Python file {file_path}: {error.msg} "
                f"at line {error.lineno}"
            ) from error

        lines = source.splitlines()
        chunks: list[CodeChunk] = []
        module_nodes: list[ast.stmt] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                chunks.append(
                    self._make_chunk(
                        source,
                        project_id=project_id,
                        file_path=file_path,
                        node=node,
                        chunk_type=self._node_type(node),
                    )
                )
            else:
                module_nodes.append(node)

        if module_nodes:
            chunks.insert(
                0,
                self._make_module_chunk(
                    lines,
                    module_nodes,
                    project_id=project_id,
                    file_path=file_path,
                ),
            )

        return chunks

    def _make_module_chunk(
        self,
        lines: list[str],
        nodes: list[ast.stmt],
        *,
        project_id: str,
        file_path: str,
    ) -> CodeChunk:
        start_line = min(node.lineno for node in nodes)
        end_line = max(node.end_lineno or node.lineno for node in nodes)
        content = "\n".join(
            "\n".join(lines[node.lineno - 1 : node.end_lineno or node.lineno])
            for node in nodes
        )
        return self._build_chunk(
            content,
            project_id=project_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type="module",
        )

    def _make_chunk(
        self,
        source: str,
        *,
        project_id: str,
        file_path: str,
        node: ast.AST,
        chunk_type: str,
    ) -> CodeChunk:
        start_line = self._start_line(node)
        end_line = getattr(node, "end_lineno", start_line)
        lines = source.splitlines()
        content = "\n".join(lines[start_line - 1 : end_line])
        return self._build_chunk(
            content,
            project_id=project_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
        )

    def _build_chunk(
        self,
        content: str,
        *,
        project_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        chunk_type: str,
    ) -> CodeChunk:
        identity = (
            f"{project_id}:{file_path}:{start_line}:{end_line}:"
            f"{chunk_type}:{content}"
        )
        chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return CodeChunk(
            project_id=project_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            chunk_id=chunk_id,
            language=self.language,
            content=content,
        )

    @staticmethod
    def _node_type(node: ast.AST) -> str:
        if isinstance(node, ast.AsyncFunctionDef):
            return "async_function"
        if isinstance(node, ast.FunctionDef):
            return "function"
        return "class"

    @staticmethod
    def _start_line(node: ast.AST) -> int:
        decorator_list = getattr(node, "decorator_list", [])
        lines = [decorator.lineno for decorator in decorator_list]
        lines.append(node.lineno)
        return min(lines)


def chunk_python_file(path: Path, *, project_id: str) -> list[CodeChunk]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ChunkingError(f"Python file is not valid UTF-8: {path}") from error

    return PythonAstChunker().chunk(
        source,
        project_id=project_id,
        file_path=path.as_posix(),
    )