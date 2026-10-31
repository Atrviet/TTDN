from app.ai.llm.gemini import _gemini_compatible_schema
from app.schemas.quiz import GeneratedQuiz


def test_gemini_schema_removes_unsupported_additional_properties_recursively() -> None:
    schema = _gemini_compatible_schema(GeneratedQuiz.model_json_schema())

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert "additionalProperties" not in keys(schema)
    assert "$defs" not in keys(schema)
    assert "$ref" not in keys(schema)
