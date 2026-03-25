"""Shared fixtures for all tests."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.core.manifest_loader import ManifestLoader
from gateway.core.runtime import RuntimeRegistry
from gateway.models.manifest import AgentManifest
from gateway.models.runtime import InvokeResponse, StreamChunk

MINIMAL_MANIFEST_YAML = """\
name: test-agent
version: "1.0.0"
description: "Test agent for unit tests"
model:
  provider: openai
  name: gpt-4o
  temperature: 0.0
tools: []
prompts:
  system: "You are a test assistant."
"""

TOOL_MANIFEST_YAML = """\
name: research-agent
version: "1.0.0"
description: "Research agent with tools"
model:
  provider: openai
  name: gpt-4o
  temperature: 0.0
tools:
  - name: calculator
    description: "Perform calculations"
    input_schema:
      expression: string
prompts:
  system: "You are a research assistant."
"""


@pytest.fixture
def tmp_manifests_dir(tmp_path):
    """A temp directory with one valid manifest YAML."""
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    (manifests_dir / "test-agent.yaml").write_text(MINIMAL_MANIFEST_YAML)
    return manifests_dir


@pytest.fixture
def sample_manifest() -> AgentManifest:
    """A pre-built AgentManifest for use in unit tests."""
    return AgentManifest.model_validate({
        "name": "test-agent",
        "version": "1.0.0",
        "description": "A test agent",
        "model": {"provider": "openai", "name": "gpt-4o", "temperature": 0.0},
        "tools": [],
        "prompts": {"system": "You are a test assistant."},
    })


@pytest.fixture
def manifest_with_tools() -> AgentManifest:
    """An AgentManifest that references the calculator tool."""
    return AgentManifest.model_validate({
        "name": "research-agent",
        "version": "1.0.0",
        "description": "Research agent",
        "model": {"provider": "openai", "name": "gpt-4o", "temperature": 0.0},
        "tools": [
            {"name": "calculator", "description": "Perform calculations", "input_schema": {"expression": "string"}}
        ],
        "prompts": {"system": "You are a research assistant."},
    })


@pytest.fixture
def mock_runtime():
    """A mock AgentRuntime that returns canned responses without hitting the LLM."""
    from unittest.mock import MagicMock

    runtime = MagicMock()
    runtime.invoke.return_value = InvokeResponse(
        thread_id="test-thread-123",
        output="Hello, I am a test response.",
        tool_calls=[],
        trace_url=None,
        latency_ms=42.0,
    )

    async def _mock_stream(message, thread_id):
        yield StreamChunk(type="token", content="Hello")
        yield StreamChunk(type="token", content=", world!")
        yield StreamChunk(type="done", content="")

    runtime.stream = _mock_stream
    return runtime


@pytest.fixture
def test_app(tmp_manifests_dir):
    """A FastAPI app with test state (no real lifespan / LLM calls)."""
    from gateway.adapters.webhook import WebhookAdapter
    from gateway.core.capability_registry import CapabilityRegistry
    from gateway.core.execution_engine import ExecutionEngine
    from gateway.routers import health, agents
    from gateway.routers import manifests as manifests_router
    from gateway.routers import openai_compat

    app = FastAPI()

    loader = ManifestLoader(str(tmp_manifests_dir))
    loader.load_all()
    registry = RuntimeRegistry()
    capability_registry = CapabilityRegistry()
    capability_registry.register("webhook", WebhookAdapter())

    app.state.manifest_loader = loader
    app.state.runtime_registry = registry
    app.state.capability_registry = capability_registry
    app.state.execution_engine = ExecutionEngine(loader, registry, capability_registry)

    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(manifests_router.router)
    app.include_router(openai_compat.router)

    @app.get("/")
    def root():
        return {
            "name": "ControlPane",
            "version": "0.1.0",
            "docs": "/docs",
            "agents": "/agents",
            "manifests": "/manifests",
        }

    return app


@pytest.fixture
def client(test_app):
    with TestClient(test_app) as c:
        yield c
