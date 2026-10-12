from collections.abc import Sequence

from qdrant_client import QdrantClient

from app.ingestion.chunker import CodeChunk
from app.retrieval.service import RetrievalService
from app.services.embeddings import EmbeddedChunk, EmbeddingService
from app.services.vector_store import QdrantVectorStore


class FakeProvider:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_retrieval_embeds_question_and_returns_citations() -> None:
    vector_store = QdrantVectorStore(
        QdrantClient(":memory:"),
        collection_name="retrieval_test",
    )
    chunk = CodeChunk(
        project_id="project-1",
        file_path="src/auth.py",
        start_line=4,
        end_line=8,
        chunk_type="function",
        chunk_id="auth",
        language="python",
        content="def authenticate(): pass",
    )
    vector_store.index_chunks(
        [
            EmbeddedChunk(chunk=chunk, vector=[1.0, 0.0, 0.0])
        ]
    )

    results = RetrievalService(
        EmbeddingService(FakeProvider()),
        vector_store,
    ).search("How does auth work?", project_id="project-1")

    assert len(results) == 1
    assert results[0].file_path == "src/auth.py"
    assert results[0].start_line == 4
    assert results[0].end_line == 8
