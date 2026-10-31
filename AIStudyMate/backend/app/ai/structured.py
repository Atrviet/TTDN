from typing import TypeVar

from pydantic import BaseModel, ValidationError


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class StructuredOutputValidationError(ValueError):
    """Raised when AI output does not conform to the application schema."""


def provider_compatible_json_schema(value: object, root: dict | None = None) -> object:
    """Convert a Pydantic schema to the JSON Schema subset accepted by Gemini.

    This only changes the schema sent to the provider. Application-side Pydantic
    validation remains authoritative and must always run on returned content.
    """
    if root is None and isinstance(value, dict):
        root = value
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/") and root is not None:
            target: object = root
            for part in reference[2:].split("/"):
                target = target[part]  # type: ignore[index]
            return provider_compatible_json_schema(target, root)
        return {
            key: provider_compatible_json_schema(item, root)
            for key, item in value.items()
            if key
            not in {
                "$defs",
                "additionalProperties",
                "title",
                "minLength",
                "maxLength",
                "minItems",
                "maxItems",
                "minimum",
                "maximum",
            }
        }
    if isinstance(value, list):
        return [provider_compatible_json_schema(item, root) for item in value]
    return value


def validate_structured_output(
    response_model: type[StructuredModel], payload: str | bytes | dict
) -> StructuredModel:
    try:
        if isinstance(payload, (str, bytes)):
            return response_model.model_validate_json(payload)
        return response_model.model_validate(payload)
    except ValidationError as exc:
        raise StructuredOutputValidationError("AI output failed schema validation") from exc
