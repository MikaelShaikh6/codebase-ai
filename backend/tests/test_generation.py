from collections.abc import Sequence

import pytest

from app.generation.service import (
    AnswerGenerationService,
    GenerationError,
    build_grounded_prompt,
)
from app.retrieval.service import RetrievedChunk


def retrieved(content: str = "def auth(): pass") -> RetrievedChunk:
    return RetrievedChunk(
        score=0.9,
        project_id="project-1",
        file_path="src/auth.py",
        start_line=4,
        end_line=6,
        chunk_type="function",
        language="python",
        content=content,
    )


class FakeGenerator:
    def __init__(self, answer: str = "Authentication is handled here.") -> None:
        self.answer = answer
        self.prompt = ""

    def generate(self, prompt: str) -> str:
        self.prompt = prompt
        return self.answer


def test_prompt_contains_question_source_and_grounding_rules() -> None:
    prompt = build_grounded_prompt("How does auth work?", [retrieved()])

    assert "How does auth work?" in prompt
    assert "src/auth.py:4-6" in prompt
    assert "Do not invent" in prompt
    assert "def auth(): pass" in prompt


def test_answer_generation_returns_answer_and_citations() -> None:
    generator = FakeGenerator()
    result = AnswerGenerationService(generator).answer(
        "How does auth work?",
        [retrieved()],
    )

    assert result.answer == "Authentication is handled here."
    assert result.citations[0].file_path == "src/auth.py"
    assert result.citations[0].start_line == 4
    assert "How does auth work?" in generator.prompt


def test_answer_generation_handles_no_retrieved_context() -> None:
    result = AnswerGenerationService(FakeGenerator()).answer("Unknown?", [])

    assert result.citations == []
    assert "could not find relevant" in result.answer


def test_answer_generation_rejects_blank_questions() -> None:
    with pytest.raises(GenerationError, match="cannot be empty"):
        AnswerGenerationService(FakeGenerator()).answer(" ", [retrieved()])


def test_ollama_generator_rejects_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"response": " "}

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: Response())

    from app.generation.service import OllamaGenerator

    with pytest.raises(GenerationError, match="empty answer"):
        OllamaGenerator().generate("prompt")


def test_ollama_generator_disables_extended_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"response": "A concise answer."}

    def fake_post(*args: object, **kwargs: object) -> Response:
        request_payload = kwargs["json"]
        assert isinstance(request_payload, dict)
        payload.update(request_payload)
        return Response()

    monkeypatch.setattr("httpx.post", fake_post)

    from app.generation.service import OllamaGenerator

    assert OllamaGenerator().generate("prompt") == "A concise answer."
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0.2, "num_predict": 120}


def test_ollama_generator_removes_thinking_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {
                "response": (
                    "Reasoning that should not be shown.\n"
                    "</think>\n"
                    "The project is a rectangle calculator."
                )
            }

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: Response())

    from app.generation.service import OllamaGenerator

    assert (
        OllamaGenerator().generate("prompt")
        == "The project is a rectangle calculator."
    )
