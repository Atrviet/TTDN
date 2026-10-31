from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from app.ai.observability import TokenUsage
from app.ai.structured import StructuredOutputValidationError, validate_structured_output
from app.ai.topics import IdentifiedTopics, LearningTopicIdentifier, TopicEvidence


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


class FakeStructuredLLM:
    model_name = "fake"

    async def generate_structured(self, **kwargs):
        return IdentifiedTopics.model_validate(
            {
                "topics": [
                    {
                        "name": "RAG",
                        "normalized_name": "rag",
                        "description": "Retrieval augmented generation",
                        "evidence_chunk_ids": ["chunk-1"],
                    }
                ]
            }
        )


def test_shared_structured_output_validation_is_strict() -> None:
    assert validate_structured_output(StrictPayload, '{"value":"ok"}').value == "ok"
    with pytest.raises(StructuredOutputValidationError):
        validate_structured_output(StrictPayload, {"value": "ok", "unexpected": True})


@pytest.mark.asyncio
async def test_topic_identifier_accepts_only_supplied_evidence_ids() -> None:
    service = LearningTopicIdentifier(FakeStructuredLLM())  # type: ignore[arg-type]
    result = await service.identify(
        [
            TopicEvidence(
                document_id=uuid4(), chunk_id="chunk-1", page_number=1, text="RAG retrieves context"
            )
        ]
    )
    assert result.topics[0].normalized_name == "rag"


def test_token_usage_rejects_negative_counts() -> None:
    assert TokenUsage(input_tokens=10, output_tokens=4).output_tokens == 4
    with pytest.raises(ValueError):
        TokenUsage(input_tokens=-1)
