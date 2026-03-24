"""API tests for GET /agents, POST /agents/{name}/invoke, POST /agents/{name}/stream."""
import json
import pytest
from unittest.mock import patch, MagicMock

from gateway.models.runtime import InvokeResponse, ToolCallRecord, StreamChunk


class TestListAgents:
    def test_returns_200(self, client):
        response = client.get("/agents")
        assert response.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/agents").json()
        assert isinstance(data, list)

    def test_contains_test_agent(self, client):
        data = client.get("/agents").json()
        names = [a["name"] for a in data]
        assert "test-agent" in names

    def test_agent_summary_fields(self, client):
        data = client.get("/agents").json()
        agent = next(a for a in data if a["name"] == "test-agent")
        assert "name" in agent
        assert "version" in agent
        assert "description" in agent
        assert "model" in agent
        assert "tools" in agent

    def test_model_field_is_provider_slash_name(self, client):
        data = client.get("/agents").json()
        agent = next(a for a in data if a["name"] == "test-agent")
        assert "/" in agent["model"]  # e.g. "openai/gpt-4o"


class TestInvokeAgent:
    def _patch_registry(self, test_app, mock_runtime):
        """Replace get_or_build on the registry so no LLM is instantiated."""
        test_app.state.runtime_registry.get_or_build = MagicMock(return_value=mock_runtime)

    def test_returns_200_on_success(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/agents/test-agent/invoke",
            json={"message": "Hello"},
        )
        assert response.status_code == 200

    def test_response_contains_output(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/agents/test-agent/invoke",
            json={"message": "Hello"},
        ).json()
        assert data["output"] == "Hello, I am a test response."

    def test_response_contains_thread_id(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/agents/test-agent/invoke",
            json={"message": "Hi", "thread_id": "my-thread"},
        ).json()
        assert data["thread_id"] == "test-thread-123"  # from mock

    def test_response_contains_latency(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/agents/test-agent/invoke",
            json={"message": "Hi"},
        ).json()
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], (int, float))

    def test_invoke_passes_message_to_runtime(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        client.post("/agents/test-agent/invoke", json={"message": "test message"})
        mock_runtime.invoke.assert_called_once()
        args = mock_runtime.invoke.call_args
        assert args[0][0] == "test message" or args[1].get("message") == "test message"

    def test_invoke_passes_thread_id(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        client.post(
            "/agents/test-agent/invoke",
            json={"message": "hi", "thread_id": "explicit-thread"},
        )
        args = mock_runtime.invoke.call_args[0]
        assert args[1] == "explicit-thread"

    def test_returns_404_for_unknown_agent(self, client):
        response = client.post(
            "/agents/ghost-agent/invoke",
            json={"message": "Hello"},
        )
        assert response.status_code == 404

    def test_404_detail_contains_agent_name(self, client):
        response = client.post(
            "/agents/ghost-agent/invoke",
            json={"message": "Hello"},
        )
        assert "ghost-agent" in response.json()["detail"]

    def test_returns_500_on_runtime_error(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        mock_runtime.invoke.side_effect = RuntimeError("LLM exploded")
        response = client.post("/agents/test-agent/invoke", json={"message": "Hi"})
        assert response.status_code == 500

    def test_500_detail_contains_error_message(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        mock_runtime.invoke.side_effect = RuntimeError("LLM exploded")
        data = client.post("/agents/test-agent/invoke", json={"message": "Hi"}).json()
        assert "LLM exploded" in data["detail"]

    def test_invoke_with_tool_calls_in_response(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        mock_runtime.invoke.return_value = InvokeResponse(
            thread_id="t1",
            output="The answer is 4",
            tool_calls=[ToolCallRecord(tool="calculator", input={"expression": "2+2"}, output="4", duration_ms=1.0)],
            trace_url=None,
            latency_ms=10.0,
        )
        data = client.post("/agents/test-agent/invoke", json={"message": "2+2"}).json()
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool"] == "calculator"

    def test_missing_message_returns_422(self, client):
        response = client.post("/agents/test-agent/invoke", json={})
        assert response.status_code == 422


class TestStreamAgent:
    def _patch_registry(self, test_app, mock_runtime):
        test_app.state.runtime_registry.get_or_build = MagicMock(return_value=mock_runtime)

    def test_returns_200(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/agents/test-agent/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 200

    def test_returns_event_stream_content_type(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/agents/test-agent/stream",
            json={"message": "Hello"},
        )
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_yields_data_events(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/agents/test-agent/stream",
            json={"message": "Hello"},
        )
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data:")]
        assert len(data_lines) > 0

    def test_stream_yields_token_chunks(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/agents/test-agent/stream",
            json={"message": "Hello"},
        )
        chunks = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                chunks.append(payload)

        token_chunks = [c for c in chunks if c["type"] == "token"]
        assert len(token_chunks) >= 1
        assert any(c["content"] == "Hello" for c in token_chunks)

    def test_stream_ends_with_done_chunk(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/agents/test-agent/stream",
            json={"message": "Hello"},
        )
        chunks = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                chunks.append(payload)

        assert chunks[-1]["type"] == "done"

    def test_stream_returns_404_for_unknown_agent(self, client):
        response = client.post(
            "/agents/ghost-agent/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 404

    def test_stream_error_yields_error_chunk(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)

        async def _error_stream(message, thread_id):
            raise RuntimeError("stream blew up")
            # Make it an async generator
            yield  # noqa: unreachable

        mock_runtime.stream = _error_stream

        response = client.post(
            "/agents/test-agent/stream",
            json={"message": "Hello"},
        )
        # The stream should complete (200) but contain an error chunk
        assert response.status_code == 200
        found_error = False
        for line in response.text.strip().split("\n"):
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
                if payload.get("type") == "error":
                    found_error = True
                    break
        assert found_error
