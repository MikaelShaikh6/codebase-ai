from __future__ import annotations

from dataclasses import dataclass

from app.services.embeddings import EmbeddingService
from app.services.vector_store import QdrantVectorStore, VectorStoreError


@dataclass(frozen=True)
class RetrievedChunk:
    score: float
    project_id: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str
    language: str
    content: str


class RetrievalService:
    def __init__(
        self,
        embeddings: EmbeddingService,
        vector_store: QdrantVectorStore,
    ) -> None:
        self.embeddings = embeddings
        self.vector_store = vector_store

    def search(
        self,
        question: str,
        *,
        project_id: str,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        vector = self.embeddings.embed_question(question)
        results = self.vector_store.search(
            vector,
            project_id=project_id,
            limit=limit,
        )

        try:
            return [
                RetrievedChunk(
                    score=result.score,
                    project_id=str(result.payload["project_id"]),
                    file_path=str(result.payload["file_path"]),
                    start_line=int(result.payload["start_line"]),
                    end_line=int(result.payload["end_line"]),
                    chunk_type=str(result.payload["chunk_type"]),
                    language=str(result.payload["language"]),
                    content=str(result.payload["content"]),
                )
                for result in results
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise VectorStoreError(
                f"Qdrant returned an invalid chunk payload: {error}"
            ) from error
