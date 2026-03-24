from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class InvokeRequest(BaseModel):
    message: str
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    tool: str
    input: dict[str, Any]
    output: str
    duration_ms: float


class InvokeResponse(BaseModel):
    thread_id: str
    output: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    trace_url: str | None = None
    latency_ms: float


class RunState(BaseModel):
    thread_id: str
    state: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentSummary(BaseModel):
    name: str
    version: str
    description: str
    model: str
    tools: list[str]


class StreamChunk(BaseModel):
    type: str  # "token" | "tool_call" | "tool_result" | "done" | "error"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
