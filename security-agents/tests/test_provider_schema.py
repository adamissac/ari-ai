import pytest
from pydantic import BaseModel, Field, ValidationError

from security_agents.llm.schema import provider_schema


class Arguments(BaseModel):
    minimum: int = Field(ge=1, le=10)


def test_provider_projection_preserves_properties_and_local_bounds():
    original = Arguments.model_json_schema()
    projected = provider_schema(original)
    assert projected["properties"]["minimum"]["type"] == "integer"
    assert "minimum" not in projected["properties"]["minimum"]
    assert "maximum" not in projected["properties"]["minimum"]
    assert original["properties"]["minimum"]["minimum"] == 1
    with pytest.raises(ValidationError):
        Arguments.model_validate({"minimum": 0})


def test_nested_definitions_and_unions_are_projected():
    schema = {"$defs": {"N": {"anyOf": [{"type": "number", "exclusiveMinimum": 0}, {"type": "null"}]}}}
    assert provider_schema(schema)["$defs"]["N"]["anyOf"][0] == {"type": "number"}
