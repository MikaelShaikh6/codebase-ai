from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

from app.ingestion.chunker import CodeChunk


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


class EmbeddingError(RuntimeError):
    """Raised when text cannot be converted into embeddings."""


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk: CodeChunk
    vector: list[float]


class FastEmbedProvider:
    """Lazy adapter around FastEmbed's local text embedding model."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL",
            DEFAULT_EMBEDDING_MODEL,
        )
        self._model: object | None = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            model = self._get_model()
            vectors = model.embed(list(texts))
            return [vector.tolist() for vector in vectors]
        except Exception as error:
            raise EmbeddingError(
                f"Could not create embeddings with model {self.model_name}: {error}"
            ) from error

    def _get_model(self) -> object:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        values = list(texts)
        if any(not text.strip() for text in values):
            raise EmbeddingError("Cannot embed empty text.")
        return self.provider.embed(values)

    def embed_chunks(self, chunks: Sequence[CodeChunk]) -> list[EmbeddedChunk]:
        vectors = self.embed_texts(chunk.content for chunk in chunks)
        if len(vectors) != len(chunks):
            raise EmbeddingError("Embedding provider returned an invalid result.")
        return [
            EmbeddedChunk(chunk=chunk, vector=vector)
            for chunk, vector in zip(chunks, vectors)
        ]

    def embed_question(self, question: str) -> list[float]:
        embeddings = self.embed_texts([question])
        return embeddings[0]
