from typing import Any
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: str = "openai"
    name: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int | None = None


class ToolInputField(BaseModel):
    type: str = "string"
    description: str = ""


class ToolDef(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)


class PromptConfig(BaseModel):
    system: str = "You are a helpful assistant."
    human: str | None = None


class StateSchema(BaseModel):
    schema_: dict[str, str] = Field(default_factory=dict, alias="schema")

    model_config = {"populate_by_name": True}


class ObservabilityConfig(BaseModel):
    trace: bool = True
    eval_tags: list[str] = Field(default_factory=list)


class AgentManifest(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    model: ModelConfig = Field(default_factory=ModelConfig)
    tools: list[ToolDef] = Field(default_factory=list)
    prompts: PromptConfig = Field(default_factory=PromptConfig)
    state: StateSchema = Field(default_factory=StateSchema)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
