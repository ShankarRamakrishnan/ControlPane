"""Unit tests for gateway/core/runtime.py."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from gateway.models.manifest import AgentManifest
from gateway.core.runtime import RuntimeRegistry


def _make_manifest(name="test-agent", version="1.0.0") -> AgentManifest:
    return AgentManifest.model_validate({
        "name": name,
        "version": version,
        "model": {"provider": "openai", "name": "gpt-4o", "temperature": 0.0},
        "tools": [],
        "prompts": {"system": "Be helpful."},
    })


# ---------------------------------------------------------------------------
# _build_llm
# ---------------------------------------------------------------------------

class TestBuildLlm:
    def test_openai_provider(self):
        from gateway.core.runtime import _build_llm
        manifest = _make_manifest()

        mock_llm = MagicMock()
        mock_openai_cls = MagicMock(return_value=mock_llm)
        with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_openai_cls)}):
            result = _build_llm(manifest)

        mock_openai_cls.assert_called_once_with(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=None,
        )
        assert result is mock_llm

    def test_anthropic_provider(self):
        from gateway.core.runtime import _build_llm
        manifest = AgentManifest.model_validate({
            "name": "a",
            "model": {"provider": "anthropic", "name": "claude-3-5-sonnet-20241022", "max_tokens": 1024},
        })

        mock_llm = MagicMock()
        mock_anthropic_cls = MagicMock(return_value=mock_llm)
        with patch.dict("sys.modules", {"langchain_anthropic": MagicMock(ChatAnthropic=mock_anthropic_cls)}):
            result = _build_llm(manifest)

        mock_anthropic_cls.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            temperature=0.0,
            max_tokens=1024,
        )
        assert result is mock_llm

    def test_unknown_provider_raises(self):
        from gateway.core.runtime import _build_llm
        manifest = AgentManifest.model_validate({
            "name": "a",
            "model": {"provider": "unknown_llm", "name": "model-x"},
        })
        with pytest.raises(ValueError, match="Unsupported model provider"):
            _build_llm(manifest)


# ---------------------------------------------------------------------------
# RuntimeRegistry
# ---------------------------------------------------------------------------

class TestRuntimeRegistry:
    def _make_mock_runtime(self, manifest):
        """Create a mock AgentRuntime without touching LLM APIs."""
        mock = MagicMock()
        mock.manifest = manifest
        return mock

    def test_builds_new_runtime(self):
        registry = RuntimeRegistry()
        manifest = _make_manifest()

        with patch("gateway.core.runtime.AgentRuntime") as MockRuntime:
            mock_instance = MagicMock()
            MockRuntime.return_value = mock_instance
            result = registry.get_or_build(manifest, mtime=1234.0)

        MockRuntime.assert_called_once_with(manifest)
        assert result is mock_instance

    def test_returns_cached_runtime_same_key(self):
        registry = RuntimeRegistry()
        manifest = _make_manifest()

        with patch("gateway.core.runtime.AgentRuntime") as MockRuntime:
            mock_instance = MagicMock()
            MockRuntime.return_value = mock_instance
            r1 = registry.get_or_build(manifest, mtime=1.0)
            r2 = registry.get_or_build(manifest, mtime=1.0)

        # Should only build once
        assert MockRuntime.call_count == 1
        assert r1 is r2

    def test_rebuilds_on_mtime_change(self):
        registry = RuntimeRegistry()
        manifest = _make_manifest()

        with patch("gateway.core.runtime.AgentRuntime") as MockRuntime:
            m1 = MagicMock()
            m2 = MagicMock()
            MockRuntime.side_effect = [m1, m2]
            r1 = registry.get_or_build(manifest, mtime=1.0)
            r2 = registry.get_or_build(manifest, mtime=2.0)

        assert MockRuntime.call_count == 2
        assert r1 is m1
        assert r2 is m2

    def test_invalidates_old_version_on_new_build(self):
        registry = RuntimeRegistry()
        manifest_v1 = _make_manifest(version="1.0.0")
        manifest_v2 = _make_manifest(version="2.0.0")

        with patch("gateway.core.runtime.AgentRuntime") as MockRuntime:
            MockRuntime.side_effect = [MagicMock(), MagicMock()]
            registry.get_or_build(manifest_v1, mtime=1.0)
            registry.get_or_build(manifest_v2, mtime=1.0)

        # Only one key per name should remain
        remaining_keys = list(registry._runtimes.keys())
        assert all("test-agent" in k for k in remaining_keys)
        assert len(remaining_keys) == 1

    def test_different_agents_do_not_invalidate_each_other(self):
        registry = RuntimeRegistry()
        m_a = _make_manifest(name="agent-a")
        m_b = _make_manifest(name="agent-b")

        with patch("gateway.core.runtime.AgentRuntime") as MockRuntime:
            MockRuntime.side_effect = [MagicMock(), MagicMock()]
            registry.get_or_build(m_a, mtime=1.0)
            registry.get_or_build(m_b, mtime=1.0)

        assert len(registry._runtimes) == 2

    def test_key_format(self):
        registry = RuntimeRegistry()
        manifest = _make_manifest(name="my-agent", version="3.0.0")

        with patch("gateway.core.runtime.AgentRuntime"):
            registry.get_or_build(manifest, mtime=99.5)

        expected_key = "my-agent:3.0.0:99.5"
        assert expected_key in registry._runtimes
