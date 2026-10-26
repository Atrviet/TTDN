from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints.chat import stream_chat_message
from app.schemas.chat import SendChatMessageRequest
from app.services.chat import PreparedChatResponse


class DisconnectedRequest:
    async def is_disconnected(self) -> bool:
        return True


class DisconnectAwareService:
    def __init__(self) -> None:
        self.persisted = False
        self.stream_closed = False
        self.llm_provider = SimpleNamespace(model_name="mock")
        self.session = SimpleNamespace(rollback=self.rollback)

    async def rollback(self) -> None:
        return None

    async def prepare_message(self, **kwargs) -> PreparedChatResponse:
        return PreparedChatResponse(
            session_id=kwargs["session_id"], user_id=kwargs["user_id"],
            message=kwargs["message"], prompt="grounded", citations=[], has_evidence=True,
        )

    async def stream_response(self, prepared):
        try:
            yield "must not be persisted"
            yield "second"
        finally:
            self.stream_closed = True

    async def persist_response(self, prepared, answer):
        self.persisted = True
        raise AssertionError("disconnected streams must not persist")


@pytest.mark.asyncio
async def test_disconnected_stream_closes_generator_without_persistence() -> None:
    service = DisconnectAwareService()
    response = await stream_chat_message(
        session_id=uuid4(),
        payload=SendChatMessageRequest(message="Question", document_ids=[uuid4()]),
        request=DisconnectedRequest(),  # type: ignore[arg-type]
        current_user=SimpleNamespace(id=uuid4()),  # type: ignore[arg-type]
        service=service,  # type: ignore[arg-type]
    )

    chunks = [chunk async for chunk in response.body_iterator]

    assert len(chunks) == 1
    assert b"event: citations" in chunks[0]
    assert service.persisted is False
    assert service.stream_closed is True
