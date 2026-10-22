from abc import ABC, abstractmethod


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
