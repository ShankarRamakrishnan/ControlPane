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


class RetryConfig(BaseModel):
    max_attempts: int = 1
    backoff: str = "exponential"  # "fixed" | "exponential"


class TriggerDef(BaseModel):
    id: str
    type: str  # "schedule" | "webhook"
    enabled: bool = True

    # schedule-specific
    cron: str | None = None
    timezone: str = "UTC"

    # webhook-specific
    secret_env: str | None = None
    event_filter: dict[str, Any] | None = None
    input_template: str | None = None

    # shared
    input: str | None = None
    thread_id: str | None = None
    retry: RetryConfig = Field(default_factory=RetryConfig)
    timeout_sec: int = 300
    dedupe_window_sec: int | None = None


class ProviderDef(BaseModel):
    """Binds an abstract capability to a concrete adapter type and config."""
    capability: str                          # e.g. "notify.message", "storage.put"
    type: str                                # adapter type: "webhook" | "openapi" | "mcp"
    config: dict[str, Any] = Field(default_factory=dict)


class OutputDef(BaseModel):
    """Declares where agent results are delivered after a run completes."""
    name: str
    provider: str                            # key into AgentManifest.providers
    on: str = "run.completed"               # event that triggers delivery


class AgentManifest(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    model: ModelConfig = Field(default_factory=ModelConfig)
    tools: list[ToolDef] = Field(default_factory=list)
    prompts: PromptConfig = Field(default_factory=PromptConfig)
    state: StateSchema = Field(default_factory=StateSchema)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    capabilities: list[str] = Field(default_factory=list)
    providers: dict[str, ProviderDef] = Field(default_factory=dict)
    triggers: list[TriggerDef] = Field(default_factory=list)
    outputs: list[OutputDef] = Field(default_factory=list)
