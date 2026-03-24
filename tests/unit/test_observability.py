"""Unit tests for gateway/core/observability.py."""
import pytest


class TestIsTracingEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
        from gateway.core import observability
        # The module-level flag was set at import time; test the function
        # by patching the private flag directly.
        monkeypatch.setattr(observability, "_langsmith_enabled", False)
        assert observability.is_tracing_enabled() is False

    def test_enabled_when_flag_set(self, monkeypatch):
        from gateway.core import observability
        monkeypatch.setattr(observability, "_langsmith_enabled", True)
        assert observability.is_tracing_enabled() is True


class TestGetTraceUrl:
    def test_returns_none_when_disabled(self, monkeypatch):
        from gateway.core import observability
        monkeypatch.setattr(observability, "_langsmith_enabled", False)
        # _client may not exist if LANGCHAIN_API_KEY was never set
        monkeypatch.setattr(observability, "_client", None, raising=False)
        assert observability.get_trace_url("some-run-id") is None

    def test_returns_url_when_enabled(self, monkeypatch):
        from unittest.mock import MagicMock
        from gateway.core import observability

        monkeypatch.setattr(observability, "_langsmith_enabled", True)
        monkeypatch.setattr(observability, "_client", MagicMock(), raising=False)
        monkeypatch.setenv("LANGCHAIN_PROJECT", "test-project")

        url = observability.get_trace_url("abc-123")
        assert url is not None
        assert "abc-123" in url
        assert "smith.langchain.com" in url
        assert "test-project" in url

    def test_uses_default_project(self, monkeypatch):
        from unittest.mock import MagicMock
        from gateway.core import observability

        monkeypatch.setattr(observability, "_langsmith_enabled", True)
        monkeypatch.setattr(observability, "_client", MagicMock(), raising=False)
        monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)

        url = observability.get_trace_url("run-xyz")
        assert "controlpane" in url


class TestSetupProjectTracing:
    def test_returns_tags_and_metadata(self, monkeypatch):
        from gateway.core.observability import setup_project_tracing
        monkeypatch.setenv("LANGCHAIN_PROJECT", "my-proj")

        config = setup_project_tracing("chat-agent")
        assert "tags" in config
        assert "chat-agent" in config["tags"]
        assert "controlpane" in config["tags"]
        assert config["metadata"]["agent"] == "chat-agent"
        assert config["metadata"]["project"] == "my-proj"

    def test_default_project_name(self, monkeypatch):
        from gateway.core.observability import setup_project_tracing
        monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)

        config = setup_project_tracing("research-agent")
        assert config["metadata"]["project"] == "controlpane"
