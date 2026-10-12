from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, Sequence

import httpx

from app.retrieval.service import RetrievedChunk


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"


class GenerationError(RuntimeError):
    """Raised when grounded answer generation fails."""


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class Citation:
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str
    citations: list[Citation]


class OllamaGenerator:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            answer = payload.get("response")
            if not isinstance(answer, str) or not answer.strip():
                raise GenerationError("Ollama returned an empty answer.")
            return answer.strip()
        except GenerationError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise GenerationError(
                f"Could not generate an answer with Ollama: {error}"
            ) from error


class AnswerGenerationService:
    def __init__(self, generator: TextGenerator) -> None:
        self.generator = generator

    def answer(
        self,
        question: str,
        chunks: Sequence[RetrievedChunk],
    ) -> GeneratedAnswer:
        if not question.strip():
            raise GenerationError("Question cannot be empty.")
        if not chunks:
            return GeneratedAnswer(
                answer="I could not find relevant project context to answer that question.",
                citations=[],
            )

        prompt = build_grounded_prompt(question, chunks)
        answer = self.generator.generate(prompt)
        citations = [
            Citation(
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
            for chunk in chunks
        ]
        return GeneratedAnswer(answer=answer, citations=citations)


def build_grounded_prompt(
    question: str,
    chunks: Sequence[RetrievedChunk],
) -> str:
    context = "\n\n".join(
        (
            f"Source: {chunk.file_path}:{chunk.start_line}-{chunk.end_line}\n"
            f"```{chunk.language}\n{chunk.content}\n```"
        )
        for chunk in chunks
    )
    return f"""You are Codebase AI, a codebase question-answering assistant.
Answer the user's question using only the supplied project context.
Do not invent files, symbols, behavior, or configuration that is not present.
Answer directly and briefly. If the context is insufficient, say so clearly.
Include relevant source references using the provided file paths and line ranges.

User question:
{question}

Project context:
{context}
"""
