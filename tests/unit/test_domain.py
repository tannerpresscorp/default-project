from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schemas.models import AgentVersionCreate


def test_agent_version_schema_is_immutable_and_requires_all_version_identifiers():
    version = AgentVersionCreate(
        code="a" * 40,
        prompt="prompt:v18",
        model_policy="models:v7",
        tool_policy="tools:v12",
        retrieval_config="retrieval:v5",
    )
    with pytest.raises(ValidationError):
        version.prompt = "different"
    with pytest.raises(ValidationError):
        AgentVersionCreate(code="abc", prompt="p", model_policy="m", tool_policy="t")


def test_tenant_id_is_not_accepted_in_agent_version_body():
    with pytest.raises(ValidationError):
        AgentVersionCreate(
            code="abc",
            prompt="p",
            model_policy="m",
            tool_policy="t",
            retrieval_config="r",
            tenant_id=uuid4(),
        )
