"""Unit tests for Pydantic models in gateway/models/."""
import uuid
import pytest
from pydantic import ValidationError

from gateway.models.manifest import (
    AgentManifest,
    ModelConfig,
    ToolDef,
    PromptConfig,
    StateSchema,
    ObservabilityConfig,
)
from gateway.models.runtime import (
    InvokeRequest,
    InvokeResponse,
    ToolCallRecord,
    StreamChunk,
    AgentSummary,
)


# ---------------------------------------------------------------------------
# ModelConfig
# ---------------------------------------------------------------------------

class TestModelConfig:
    def test_defaults(self):
        cfg = ModelConfig()
        assert cfg.provider == "openai"
        assert cfg.name == "gpt-4o"
        assert cfg.temperature == 0.0
        assert cfg.max_tokens is None

    def test_anthropic_provider(self):
        cfg = ModelConfig(provider="anthropic", name="claude-3-5-sonnet-20241022")
        assert cfg.provider == "anthropic"
        assert cfg.name == "claude-3-5-sonnet-20241022"

    def test_custom_temperature_and_tokens(self):
        cfg = ModelConfig(temperature=0.7, max_tokens=2048)
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048


# ---------------------------------------------------------------------------
# ToolDef
# ---------------------------------------------------------------------------

class TestToolDef:
    def test_required_fields(self):
        t = ToolDef(name="calculator", description="does math")
        assert t.name == "calculator"
        assert t.description == "does math"
        assert t.input_schema == {}

    def test_with_input_schema(self):
        t = ToolDef(name="search", description="searches", input_schema={"query": "string"})
        assert t.input_schema == {"query": "string"}

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ToolDef(description="oops")


# ---------------------------------------------------------------------------
# PromptConfig
# ---------------------------------------------------------------------------

class TestPromptConfig:
    def test_defaults(self):
        p = PromptConfig()
        assert p.system == "You are a helpful assistant."
        assert p.human is None

    def test_custom(self):
        p = PromptConfig(system="Be concise.", human="Answer: {question}")
        assert p.system == "Be concise."
        assert p.human == "Answer: {question}"


# ---------------------------------------------------------------------------
# StateSchema
# ---------------------------------------------------------------------------

class TestStateSchema:
    def test_defaults(self):
        s = StateSchema()
        assert s.schema_ == {}

    def test_alias(self):
        s = StateSchema.model_validate({"schema": {"messages": "list"}})
        assert s.schema_ == {"messages": "list"}


# ---------------------------------------------------------------------------
# ObservabilityConfig
# ---------------------------------------------------------------------------

class TestObservabilityConfig:
    def test_defaults(self):
        o = ObservabilityConfig()
        assert o.trace is True
        assert o.eval_tags == []

    def test_tags(self):
        o = ObservabilityConfig(trace=False, eval_tags=["prod", "v2"])
        assert o.trace is False
        assert o.eval_tags == ["prod", "v2"]


# ---------------------------------------------------------------------------
# AgentManifest
# ---------------------------------------------------------------------------

class TestAgentManifest:
    def test_minimal_valid(self):
        m = AgentManifest(name="my-agent")
        assert m.name == "my-agent"
        assert m.version == "1.0.0"
        assert m.description == ""
        assert m.tools == []

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            AgentManifest.model_validate({})

    def test_full_manifest(self):
        raw = {
            "name": "research-agent",
            "version": "2.0.0",
            "description": "does research",
            "model": {"provider": "anthropic", "name": "claude-3-5-sonnet-20241022"},
            "tools": [{"name": "web_search", "description": "searches web"}],
            "prompts": {"system": "You are a researcher."},
            "state": {"schema": {"messages": "list"}},
            "observability": {"trace": True, "eval_tags": ["research"]},
        }
        m = AgentManifest.model_validate(raw)
        assert m.name == "research-agent"
        assert m.version == "2.0.0"
        assert len(m.tools) == 1
        assert m.tools[0].name == "web_search"
        assert m.model.provider == "anthropic"
        assert m.observability.eval_tags == ["research"]


# ---------------------------------------------------------------------------
# InvokeRequest
# ---------------------------------------------------------------------------

class TestInvokeRequest:
    def test_required_message(self):
        req = InvokeRequest(message="Hello")
        assert req.message == "Hello"

    def test_auto_thread_id(self):
        req = InvokeRequest(message="Hi")
        # Should be a valid UUID
        uuid.UUID(req.thread_id)

    def test_explicit_thread_id(self):
        req = InvokeRequest(message="Hi", thread_id="my-thread")
        assert req.thread_id == "my-thread"

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            InvokeRequest.model_validate({})

    def test_metadata_defaults_empty(self):
        req = InvokeRequest(message="Hi")
        assert req.metadata == {}


# ---------------------------------------------------------------------------
# ToolCallRecord
# ---------------------------------------------------------------------------

class TestToolCallRecord:
    def test_fields(self):
        rec = ToolCallRecord(tool="calculator", input={"expression": "2+2"}, output="4", duration_ms=5.5)
        assert rec.tool == "calculator"
        assert rec.input == {"expression": "2+2"}
        assert rec.output == "4"
        assert rec.duration_ms == 5.5


# ---------------------------------------------------------------------------
# InvokeResponse
# ---------------------------------------------------------------------------

class TestInvokeResponse:
    def test_fields(self):
        resp = InvokeResponse(thread_id="t1", output="done", latency_ms=10.0)
        assert resp.thread_id == "t1"
        assert resp.output == "done"
        assert resp.tool_calls == []
        assert resp.trace_url is None
        assert resp.latency_ms == 10.0

    def test_with_tool_calls(self):
        rec = ToolCallRecord(tool="calc", input={}, output="42", duration_ms=1.0)
        resp = InvokeResponse(thread_id="t1", output="42", latency_ms=5.0, tool_calls=[rec])
        assert len(resp.tool_calls) == 1


# ---------------------------------------------------------------------------
# StreamChunk
# ---------------------------------------------------------------------------

class TestStreamChunk:
    def test_token_chunk(self):
        chunk = StreamChunk(type="token", content="hello")
        assert chunk.type == "token"
        assert chunk.content == "hello"
        assert chunk.metadata == {}

    def test_done_chunk(self):
        chunk = StreamChunk(type="done", content="")
        assert chunk.type == "done"

    def test_error_chunk(self):
        chunk = StreamChunk(type="error", content="something went wrong")
        assert chunk.type == "error"

    def test_tool_call_chunk_with_metadata(self):
        chunk = StreamChunk(type="tool_call", content="calculator", metadata={"input": "2+2"})
        assert chunk.metadata == {"input": "2+2"}


# ---------------------------------------------------------------------------
# AgentSummary
# ---------------------------------------------------------------------------

class TestAgentSummary:
    def test_fields(self):
        s = AgentSummary(name="agent", version="1.0", description="test", model="openai/gpt-4o", tools=["calc"])
        assert s.name == "agent"
        assert s.tools == ["calc"]
