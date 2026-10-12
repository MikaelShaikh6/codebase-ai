from qdrant_client import QdrantClient

import pytest

from app.ingestion.chunker import CodeChunk
from app.services.embeddings import EmbeddedChunk
from app.services.vector_store import QdrantVectorStore, VectorStoreError


def embedded(
    chunk_id: str,
    project_id: str = "project-1",
    vector: list[float] | None = None,
) -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk=CodeChunk(
            project_id=project_id,
            file_path=f"{chunk_id}.py",
            start_line=1,
            end_line=2,
            chunk_type="function",
            chunk_id=chunk_id,
            language="python",
            content=f"def {chunk_id}(): pass",
        ),
        vector=vector or [1.0, 0.0, 0.0],
    )


def store() -> QdrantVectorStore:
    return QdrantVectorStore(
        QdrantClient(":memory:"),
        collection_name="test_chunks",
    )


def test_index_chunks_creates_collection_and_payload() -> None:
    vector_store = store()

    result = vector_store.index_chunks([embedded("chunk-1")])
    points = vector_store.client.retrieve(
        collection_name="test_chunks",
        ids=[vector_store.client.scroll("test_chunks", limit=1)[0][0].id],
        with_payload=True,
    )

    assert result.indexed_count == 1
    assert points[0].payload["project_id"] == "project-1"
    assert points[0].payload["file_path"] == "chunk-1.py"
    assert points[0].payload["start_line"] == 1


def test_index_chunks_rejects_mixed_projects() -> None:
    with pytest.raises(VectorStoreError, match="one project"):
        store().index_chunks([embedded("one"), embedded("two", "project-2")])


def test_index_chunks_rejects_inconsistent_vector_sizes() -> None:
    with pytest.raises(VectorStoreError, match="same non-zero size"):
        store().index_chunks(
            [embedded("one"), embedded("two", vector=[1.0, 0.0])]
        )


def test_delete_project_removes_only_matching_payloads() -> None:
    vector_store = store()
    vector_store.index_chunks([embedded("one", "project-1")])
    vector_store.index_chunks([embedded("two", "project-2")])

    vector_store.delete_project("project-1")
    points, _ = vector_store.client.scroll("test_chunks", limit=10, with_payload=True)

    assert len(points) == 1
    assert points[0].payload["project_id"] == "project-2"


def test_search_filters_results_to_project() -> None:
    vector_store = store()
    vector_store.index_chunks([embedded("one", "project-1")])
    vector_store.index_chunks([embedded("two", "project-2")])

    results = vector_store.search(
        [1.0, 0.0, 0.0],
        project_id="project-1",
    )

    assert len(results) == 1
    assert results[0].payload["project_id"] == "project-1"


def test_search_rejects_empty_vector() -> None:
    with pytest.raises(VectorStoreError, match="empty vector"):
        store().search([], project_id="project-1")
