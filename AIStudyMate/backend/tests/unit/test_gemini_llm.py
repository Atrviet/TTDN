from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.ai.llm.base import LLMError
from app.ai.llm.gemini import GeminiLLMProvider


class FakeModels:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.kwargs = None

    async def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response

    async def generate_content_stream(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeStream:
    def __init__(self, parts: list[str]) -> None:
        self.parts = iter(parts)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return SimpleNamespace(text=next(self.parts))
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def aclose(self) -> None:
        self.closed = True


class StructuredResponse(BaseModel):
    value: str


def provider() -> GeminiLLMProvider:
    return GeminiLLMProvider(
        api_key="test-key",
        model_name="test-model",
        timeout_seconds=10,
        max_retries=2,
        max_output_tokens=256,
    )


@pytest.mark.asyncio
async def test_gemini_generation_uses_configured_model_and_system_instruction() -> None:
    llm = provider()
    models = FakeModels(response=SimpleNamespace(text="  grounded answer  "))
    llm.client = SimpleNamespace(aio=SimpleNamespace(models=models))

    answer = await llm.generate(system_instruction="system", prompt="prompt")

    assert answer == "grounded answer"
    assert models.kwargs["model"] == "test-model"
    assert models.kwargs["contents"] == "prompt"
    assert models.kwargs["config"].system_instruction == "system"


@pytest.mark.asyncio
async def test_gemini_generation_wraps_provider_failure() -> None:
    llm = provider()
    llm.client = SimpleNamespace(
        aio=SimpleNamespace(models=FakeModels(error=TimeoutError("timeout")))
    )

    with pytest.raises(LLMError, match="Gemini generation request failed"):
        await llm.generate(system_instruction="system", prompt="prompt")


@pytest.mark.asyncio
async def test_gemini_generation_requires_api_key_only_when_called() -> None:
    llm = GeminiLLMProvider(
        api_key="",
        model_name="test-model",
        timeout_seconds=10,
        max_retries=2,
        max_output_tokens=256,
    )
    with pytest.raises(LLMError, match="not configured"):
        await llm.generate(system_instruction="system", prompt="prompt")


@pytest.mark.asyncio
async def test_gemini_structured_generation_validates_pydantic_output() -> None:
    llm = provider()
    models = FakeModels(
        response=SimpleNamespace(parsed=StructuredResponse(value="valid"), text=None)
    )
    llm.client = SimpleNamespace(aio=SimpleNamespace(models=models))

    result = await llm.generate_structured(
        system_instruction="system",
        prompt="prompt",
        response_model=StructuredResponse,
        max_output_tokens=512,
    )

    assert result.value == "valid"
    config = models.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema == StructuredResponse
    assert config.max_output_tokens == 512


@pytest.mark.asyncio
async def test_gemini_stream_yields_fragments_and_closes_transport() -> None:
    llm = provider()
    stream = FakeStream(["Xin ", "chào"])
    models = FakeModels(response=stream)
    llm.client = SimpleNamespace(aio=SimpleNamespace(models=models))

    fragments = [item async for item in llm.stream(system_instruction="system", prompt="prompt")]

    assert fragments == ["Xin ", "chào"]
    assert stream.closed is True
    assert models.kwargs["model"] == "test-model"
