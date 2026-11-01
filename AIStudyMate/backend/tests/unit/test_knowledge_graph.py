import pytest
from pydantic import ValidationError
from app.schemas.knowledge_graph import ExtractedKnowledge
from app.services.knowledge_graph import normalize_concept_name


def test_normalization_preserves_vietnamese_and_deduplicates_formatting():
    assert normalize_concept_name("  Vòng_lặp FOR! ") == "vòng lặp for"
    assert normalize_concept_name("VÒNG  LẶP-for") == "vòng lặp for"


def test_structured_output_validates_relationship_types_and_confidence():
    valid=ExtractedKnowledge.model_validate({"concepts":[{"name":"A","definition":"Definition","source_chunk_id":"c1","confidence":.7}],"relations":[]})
    assert valid.concepts[0].name=="A"
    with pytest.raises(ValidationError):
        ExtractedKnowledge.model_validate({"concepts":[],"relations":[{"source":"A","target":"B","relation_type":"causes","source_chunk_id":"c1","confidence":.5}]})
    with pytest.raises(ValidationError):
        ExtractedKnowledge.model_validate({"concepts":[],"relations":[{"source":"A","target":"A","relation_type":"related_to","source_chunk_id":"c1","confidence":1.1}]})
