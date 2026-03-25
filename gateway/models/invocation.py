from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


class InvocationSource(str, Enum):
    manual = "manual"
    schedule = "schedule"
    webhook = "webhook"


class InvocationContext(BaseModel):
    trigger_id: str | None = None
    event_payload: dict[str, Any] | None = None


class UnifiedInvocationRequest(BaseModel):
    agent: str
    source: InvocationSource
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input: str
    context: InvocationContext = Field(default_factory=InvocationContext)
    metadata: dict[str, Any] = Field(default_factory=dict)
