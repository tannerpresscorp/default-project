from pydantic import BaseModel, ConfigDict, Field


class AgentVersionCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=200)
    model_policy: str = Field(min_length=1, max_length=200)
    tool_policy: str = Field(min_length=1, max_length=200)
    retrieval_config: str = Field(min_length=1, max_length=200)
