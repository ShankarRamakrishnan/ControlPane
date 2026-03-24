"""API tests for the OpenAI-compatible endpoints (/openai/v1/...)."""
import json
import pytest
from unittest.mock import MagicMock

from gateway.models.runtime import InvokeResponse, StreamChunk


class TestListModels:
    def test_returns_200(self, client):
        response = client.get("/openai/v1/models")
        assert response.status_code == 200

    def test_response_shape(self, client):
        data = client.get("/openai/v1/models").json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)

    def test_contains_loaded_agent(self, client):
        data = client.get("/openai/v1/models").json()
        ids = [m["id"] for m in data["data"]]
        assert "test-agent" in ids

    def test_model_object_fields(self, client):
        data = client.get("/openai/v1/models").json()
        assert len(data["data"]) > 0
        model = data["data"][0]
        assert "id" in model
        assert "object" in model
        assert "created" in model
        assert "owned_by" in model

    def test_owned_by_controlpane(self, client):
        data = client.get("/openai/v1/models").json()
        for model in data["data"]:
            assert model["owned_by"] == "controlpane"


class TestChatCompletionsSync:
    def _patch_registry(self, test_app, mock_runtime):
        test_app.state.runtime_registry.get_or_build = MagicMock(return_value=mock_runtime)

    def test_returns_200(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 200

    def test_response_shape(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        ).json()
        assert data["object"] == "chat.completion"
        assert "choices" in data
        assert len(data["choices"]) == 1

    def test_choice_contains_assistant_message(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        ).json()
        choice = data["choices"][0]
        assert choice["message"]["role"] == "assistant"
        assert choice["message"]["content"] == "Hello, I am a test response."

    def test_finish_reason_is_stop(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        ).json()
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_uses_last_user_message(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [
                    {"role": "user", "content": "First message"},
                    {"role": "assistant", "content": "OK"},
                    {"role": "user", "content": "Last message"},
                ],
            },
        )
        args = mock_runtime.invoke.call_args[0]
        assert args[0] == "Last message"

    def test_returns_404_for_unknown_agent(self, client):
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "ghost-agent",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )
        assert response.status_code == 404

    def test_returns_400_when_no_user_message(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "system", "content": "You are helpful."}],
            },
        )
        assert response.status_code == 400

    def test_400_detail_for_no_user_message(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "system", "content": "Be helpful."}],
            },
        ).json()
        assert "user" in data["detail"].lower()

    def test_returns_500_on_runtime_error(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        mock_runtime.invoke.side_effect = RuntimeError("boom")
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )
        assert response.status_code == 500

    def test_response_contains_id_and_created(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        ).json()
        assert "id" in data
        assert data["id"].startswith("chatcmpl-")
        assert "created" in data

    def test_usage_field_present(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        data = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        ).json()
        assert "usage" in data


class TestChatCompletionsStream:
    def _patch_registry(self, test_app, mock_runtime):
        test_app.state.runtime_registry.get_or_build = MagicMock(return_value=mock_runtime)

    def test_returns_200(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200

    def test_returns_event_stream_content_type(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_emits_sse_chunks(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data:") and l != "data: [DONE]"]
        assert len(data_lines) > 0

    def test_stream_chunks_are_chat_completion_chunk_objects(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        for line in response.text.strip().split("\n"):
            if line.startswith("data:") and line.strip() != "data: [DONE]":
                chunk = json.loads(line[len("data:"):].strip())
                assert chunk["object"] == "chat.completion.chunk"
                assert "choices" in chunk
                break

    def test_stream_ends_with_done_sentinel(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert "data: [DONE]" in response.text

    def test_stream_chunk_model_matches_agent(self, test_app, client, mock_runtime):
        self._patch_registry(test_app, mock_runtime)
        response = client.post(
            "/openai/v1/chat/completions",
            json={
                "model": "test-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        for line in response.text.strip().split("\n"):
            if line.startswith("data:") and line.strip() != "data: [DONE]":
                chunk = json.loads(line[len("data:"):].strip())
                assert chunk["model"] == "test-agent"
                break
