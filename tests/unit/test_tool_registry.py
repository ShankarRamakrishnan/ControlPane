"""Unit tests for gateway/core/tool_registry.py."""
import sys
import textwrap
import pytest
from unittest.mock import MagicMock, patch

from gateway.models.manifest import AgentManifest, ToolDef


# We patch the module-level registry to keep tests isolated.
def _fresh_registry():
    """Return a fresh empty registry dict and patch it into the module."""
    import gateway.core.tool_registry as reg_mod
    return reg_mod


class TestRegister:
    def test_registers_tool_by_name(self, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        fake_registry = {}
        monkeypatch.setattr(reg_mod, "_tool_registry", fake_registry)

        fake_tool = MagicMock()
        fake_tool.name = "my_tool"

        result = reg_mod.register(fake_tool)
        assert "my_tool" in fake_registry
        assert fake_registry["my_tool"] is fake_tool
        # register returns the tool unchanged (decorator pattern)
        assert result is fake_tool

    def test_overwrites_existing_name(self, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        fake_registry = {}
        monkeypatch.setattr(reg_mod, "_tool_registry", fake_registry)

        tool_v1 = MagicMock()
        tool_v1.name = "shared"
        tool_v2 = MagicMock()
        tool_v2.name = "shared"

        reg_mod.register(tool_v1)
        reg_mod.register(tool_v2)
        assert fake_registry["shared"] is tool_v2


class TestListRegistered:
    def test_returns_registered_names(self, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        t1 = MagicMock()
        t1.name = "tool_a"
        t2 = MagicMock()
        t2.name = "tool_b"
        monkeypatch.setattr(reg_mod, "_tool_registry", {"tool_a": t1, "tool_b": t2})
        names = reg_mod.list_registered()
        assert set(names) == {"tool_a", "tool_b"}

    def test_empty_registry(self, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        monkeypatch.setattr(reg_mod, "_tool_registry", {})
        assert reg_mod.list_registered() == []


class TestLoadToolsForManifest:
    def _make_manifest(self, tool_names: list[str]) -> AgentManifest:
        return AgentManifest.model_validate({
            "name": "test",
            "tools": [{"name": n, "description": "d"} for n in tool_names],
        })

    def test_returns_matching_tools(self, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        t = MagicMock()
        t.name = "calculator"
        monkeypatch.setattr(reg_mod, "_tool_registry", {"calculator": t})

        manifest = self._make_manifest(["calculator"])
        result = reg_mod.load_tools_for_manifest(manifest)
        assert result == [t]

    def test_missing_tool_returns_empty_and_warns(self, monkeypatch, caplog):
        import gateway.core.tool_registry as reg_mod
        import logging
        monkeypatch.setattr(reg_mod, "_tool_registry", {})

        manifest = self._make_manifest(["nonexistent"])
        with caplog.at_level(logging.WARNING):
            result = reg_mod.load_tools_for_manifest(manifest)
        assert result == []
        assert "nonexistent" in caplog.text

    def test_no_tools_in_manifest(self, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        monkeypatch.setattr(reg_mod, "_tool_registry", {})
        manifest = self._make_manifest([])
        assert reg_mod.load_tools_for_manifest(manifest) == []

    def test_partial_tools_available(self, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        t = MagicMock()
        t.name = "calculator"
        monkeypatch.setattr(reg_mod, "_tool_registry", {"calculator": t})

        manifest = self._make_manifest(["calculator", "web_search"])
        result = reg_mod.load_tools_for_manifest(manifest)
        assert len(result) == 1
        assert result[0].name == "calculator"


class TestDiscoverTools:
    def test_missing_dir_returns_zero(self, tmp_path):
        import gateway.core.tool_registry as reg_mod
        count = reg_mod.discover_tools(str(tmp_path / "nonexistent"))
        assert count == 0

    def test_skips_dunder_files(self, tmp_path):
        import gateway.core.tool_registry as reg_mod
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "__pycache__").mkdir()
        count = reg_mod.discover_tools(str(tmp_path))
        assert count == 0

    def test_imports_valid_module(self, tmp_path, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        # Write a simple .py file that doesn't call register
        module_content = textwrap.dedent("""\
            def hello():
                return "world"
        """)
        (tmp_path / "simple_tool.py").write_text(module_content)

        # Remove from sys.modules if already present
        mod_name = "tools.simple_tool"
        monkeypatch.delitem(sys.modules, mod_name, raising=False)

        count = reg_mod.discover_tools(str(tmp_path))
        assert count == 0
        assert mod_name in sys.modules

    def test_skips_already_imported_module(self, tmp_path, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        (tmp_path / "dup_tool.py").write_text("x = 1")

        # Pre-populate sys.modules to simulate already-imported
        fake_mod = MagicMock()
        monkeypatch.setitem(sys.modules, "tools.dup_tool", fake_mod)

        count = reg_mod.discover_tools(str(tmp_path))
        assert count == 0

    def test_handles_import_error_gracefully(self, tmp_path, monkeypatch):
        import gateway.core.tool_registry as reg_mod
        (tmp_path / "broken_tool.py").write_text("raise RuntimeError('boom')")

        mod_name = "tools.broken_tool"
        monkeypatch.delitem(sys.modules, mod_name, raising=False)

        # Should not raise — just logs an error
        count = reg_mod.discover_tools(str(tmp_path))
        assert count == 0
