from collections.abc import Sequence

import pytest

from app.ingestion.chunker import CodeChunk
from app.services.embeddings import (
    EmbeddingError,
    EmbeddingService,
    FastEmbedProvider,
)


class FakeProvider:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(index), float(len(text))] for index, text in enumerate(texts)]


def chunk(content: str) -> CodeChunk:
    return CodeChunk(
        project_id="project-1",
        file_path="main.py",
        start_line=1,
        end_line=1,
        chunk_type="module",
        chunk_id="chunk-1",
        language="python",
        content=content,
    )


def test_embedding_service_embeds_texts_in_order() -> None:
    service = EmbeddingService(FakeProvider())

    assert service.embed_texts(["first", "second"]) == [
        [0.0, 5.0],
        [1.0, 6.0],
    ]


def test_embedding_service_embeds_chunks_with_metadata() -> None:
    service = EmbeddingService(FakeProvider())

    embedded = service.embed_chunks([chunk("source")])

    assert embedded[0].chunk.file_path == "main.py"
    assert embedded[0].vector == [0.0, 6.0]


def test_embedding_service_embeds_question() -> None:
    service = EmbeddingService(FakeProvider())

    assert service.embed_question("How does auth work?") == [0.0, 19.0]


def test_embedding_service_rejects_blank_text() -> None:
    with pytest.raises(EmbeddingError, match="empty text"):
        EmbeddingService(FakeProvider()).embed_texts(["  "])


def test_embedding_service_rejects_provider_length_mismatch() -> None:
    class BadProvider:
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return []

    with pytest.raises(EmbeddingError, match="invalid result"):
        EmbeddingService(BadProvider()).embed_chunks([chunk("source")])


def test_fastembed_provider_loads_model_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FastEmbedProvider(model_name="test-model")

    assert provider.model_name == "test-model"
    assert provider._model is None
