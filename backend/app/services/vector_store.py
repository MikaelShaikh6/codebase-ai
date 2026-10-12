from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.services.embeddings import EmbeddedChunk


DEFAULT_COLLECTION_NAME = "codebase_chunks"


class VectorStoreError(RuntimeError):
    """Raised when chunks cannot be indexed in Qdrant."""


@dataclass(frozen=True)
class IndexResult:
    project_id: str
    indexed_count: int
    collection_name: str


@dataclass(frozen=True)
class VectorSearchResult:
    score: float
    payload: dict[str, object]


class QdrantVectorStore:
    def __init__(
        self,
        client: QdrantClient | None = None,
        *,
        collection_name: str | None = None,
    ) -> None:
        self.client = client or self._create_client()
        self.collection_name = collection_name or os.getenv(
            "QDRANT_COLLECTION",
            DEFAULT_COLLECTION_NAME,
        )

    def index_chunks(
        self,
        embedded_chunks: list[EmbeddedChunk],
    ) -> IndexResult:
        if not embedded_chunks:
            raise VectorStoreError("Cannot index an empty chunk list.")

        project_ids = {item.chunk.project_id for item in embedded_chunks}
        if len(project_ids) != 1:
            raise VectorStoreError("All chunks must belong to one project.")

        vector_size = len(embedded_chunks[0].vector)
        if vector_size == 0 or any(
            len(item.vector) != vector_size for item in embedded_chunks
        ):
            raise VectorStoreError("All vectors must have the same non-zero size.")

        self._ensure_collection(vector_size)
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, item.chunk.chunk_id)),
                vector=item.vector,
                payload={
                    "project_id": item.chunk.project_id,
                    "file_path": item.chunk.file_path,
                    "start_line": item.chunk.start_line,
                    "end_line": item.chunk.end_line,
                    "chunk_type": item.chunk.chunk_type,
                    "chunk_id": item.chunk.chunk_id,
                    "language": item.chunk.language,
                    "content": item.chunk.content,
                },
            )
            for item in embedded_chunks
        ]

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        except Exception as error:
            raise VectorStoreError(
                f"Could not index chunks in {self.collection_name}: {error}"
            ) from error

        return IndexResult(
            project_id=next(iter(project_ids)),
            indexed_count=len(points),
            collection_name=self.collection_name,
        )

    def delete_project(self, project_id: str) -> None:
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="project_id",
                                match=models.MatchValue(value=project_id),
                            )
                        ]
                    )
                ),
                wait=True,
            )
        except Exception as error:
            raise VectorStoreError(
                f"Could not delete project {project_id} from Qdrant: {error}"
            ) from error

    def search(
        self,
        vector: list[float],
        *,
        project_id: str,
        limit: int = 5,
    ) -> list[VectorSearchResult]:
        if not vector:
            raise VectorStoreError("Cannot search with an empty vector.")
        if limit < 1:
            raise VectorStoreError("Search limit must be positive.")

        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="project_id",
                            match=models.MatchValue(value=project_id),
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
            )
        except Exception as error:
            raise VectorStoreError(
                f"Could not search {self.collection_name}: {error}"
            ) from error

        return [
            VectorSearchResult(
                score=point.score,
                payload=dict(point.payload or {}),
            )
            for point in response.points
        ]

    def _ensure_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.collection_name):
            info = self.client.get_collection(self.collection_name)
            configured_size = info.config.params.vectors.size
            if configured_size != vector_size:
                raise VectorStoreError(
                    f"Collection expects vectors of size {configured_size}, "
                    f"received {vector_size}."
                )
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    @staticmethod
    def _create_client() -> QdrantClient:
        url = os.getenv("QDRANT_URL")
        if url:
            return QdrantClient(
                url=url,
                api_key=os.getenv("QDRANT_API_KEY"),
            )
        return QdrantClient(path=os.getenv("QDRANT_PATH", "data/qdrant"))
