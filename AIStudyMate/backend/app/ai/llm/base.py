from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class LLMError(Exception):
    """Raised when the configured language model cannot generate an answer."""


class LLMProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, *, system_instruction: str, prompt: str) -> str:
        raise NotImplementedError

    async def generate_structured(
        self,
        *,
        system_instruction: str,
        prompt: str,
        response_model: type[StructuredModel],
        max_output_tokens: int | None = None,
    ) -> StructuredModel:
        raise LLMError("Structured output is not supported by this provider")

    async def stream(self, *, system_instruction: str, prompt: str) -> AsyncIterator[str]:
        """Stream text fragments. Providers without native streaming remain compatible."""
        yield await self.generate(system_instruction=system_instruction, prompt=prompt)
