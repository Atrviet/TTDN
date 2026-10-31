import asyncio
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.ai.llm.base import LLMError, LLMProvider, StructuredModel
from app.ai.structured import provider_compatible_json_schema


_gemini_compatible_schema = provider_compatible_json_schema


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout_seconds: float,
        max_retries: int,
        max_output_tokens: int,
        max_concurrent_requests: int = 4,
    ) -> None:
        self.api_key = api_key
        self._model_name = model_name
        self.max_output_tokens = max_output_tokens
        self._request_slots = asyncio.Semaphore(max_concurrent_requests)
        self.http_options = types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=max_retries,
                    initial_delay=1.0,
                    max_delay=10.0,
                    exp_base=2.0,
                    jitter=0.5,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            )
        self.client = None

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(self, *, system_instruction: str, prompt: str) -> str:
        if not self.api_key:
            raise LLMError("Gemini API key is not configured")
        await self._request_slots.acquire()
        try:
            if self.client is None:
                self.client = genai.Client(api_key=self.api_key, http_options=self.http_options)
            response = await self.client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    max_output_tokens=self.max_output_tokens,
                ),
            )
            answer = (response.text or "").strip()
            if not answer:
                raise LLMError("Gemini returned an empty response")
            return answer
        except LLMError:
            raise
        except (errors.APIError, TimeoutError, OSError) as exc:
            raise LLMError("Gemini generation request failed") from exc
        except Exception as exc:
            raise LLMError("Gemini generation request failed") from exc
        finally:
            self._request_slots.release()

    async def generate_structured(
        self,
        *,
        system_instruction: str,
        prompt: str,
        response_model: type[StructuredModel],
        max_output_tokens: int | None = None,
    ) -> StructuredModel:
        if not self.api_key:
            raise LLMError("Gemini API key is not configured")
        await self._request_slots.acquire()
        try:
            if self.client is None:
                self.client = genai.Client(api_key=self.api_key, http_options=self.http_options)
            response = await self.client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    max_output_tokens=max_output_tokens or self.max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=_gemini_compatible_schema(response_model.model_json_schema()),
                ),
            )
            if isinstance(response.parsed, response_model):
                return response.parsed
            if not response.text:
                raise LLMError("Gemini returned an empty structured response")
            return response_model.model_validate_json(response.text)
        except (LLMError, ValidationError):
            raise
        except (errors.APIError, TimeoutError, OSError) as exc:
            raise LLMError("Gemini structured generation request failed") from exc
        except Exception as exc:
            raise LLMError("Gemini structured generation request failed") from exc
        finally:
            self._request_slots.release()

    async def stream(self, *, system_instruction: str, prompt: str) -> AsyncIterator[str]:
        if not self.api_key:
            raise LLMError("Gemini API key is not configured")
        stream = None
        await self._request_slots.acquire()
        try:
            if self.client is None:
                self.client = genai.Client(api_key=self.api_key, http_options=self.http_options)
            stream = await self.client.aio.models.generate_content_stream(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    max_output_tokens=self.max_output_tokens,
                ),
            )
            emitted = False
            async for response in stream:
                text = response.text or ""
                if text:
                    emitted = True
                    yield text
            if not emitted:
                raise LLMError("Gemini returned an empty response")
        except LLMError:
            raise
        except (errors.APIError, TimeoutError, OSError) as exc:
            raise LLMError("Gemini streaming request failed") from exc
        except Exception as exc:
            raise LLMError("Gemini streaming request failed") from exc
        finally:
            try:
                close = getattr(stream, "aclose", None)
                if close is not None:
                    await close()
            finally:
                self._request_slots.release()
