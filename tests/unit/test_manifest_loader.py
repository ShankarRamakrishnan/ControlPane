"""Unit tests for gateway/core/manifest_loader.py."""
import time
import pytest

from gateway.core.manifest_loader import ManifestLoader
from gateway.models.manifest import AgentManifest

VALID_YAML = """\
name: my-agent
version: "1.0.0"
description: "A test agent"
model:
  provider: openai
  name: gpt-4o
  temperature: 0.0
tools: []
prompts:
  system: "Be helpful."
"""

INVALID_YAML = """\
this: is: not: valid: yaml: [
"""

MISSING_NAME_YAML = """\
version: "1.0.0"
description: "No name field"
"""


class TestManifestLoaderLoadAll:
    def test_empty_dir(self, tmp_path):
        loader = ManifestLoader(str(tmp_path))
        result = loader.load_all()
        assert result == {}

    def test_missing_dir(self, tmp_path):
        loader = ManifestLoader(str(tmp_path / "nonexistent"))
        result = loader.load_all()
        assert result == {}

    def test_loads_valid_yaml(self, tmp_path):
        (tmp_path / "my-agent.yaml").write_text(VALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        result = loader.load_all()
        assert "my-agent" in result
        assert isinstance(result["my-agent"], AgentManifest)
        assert result["my-agent"].name == "my-agent"

    def test_skips_invalid_yaml(self, tmp_path):
        (tmp_path / "bad.yaml").write_text(INVALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        result = loader.load_all()
        assert result == {}

    def test_skips_missing_required_field(self, tmp_path):
        (tmp_path / "no-name.yaml").write_text(MISSING_NAME_YAML)
        loader = ManifestLoader(str(tmp_path))
        result = loader.load_all()
        assert result == {}

    def test_loads_multiple_manifests(self, tmp_path):
        (tmp_path / "agent-a.yaml").write_text(VALID_YAML.replace("my-agent", "agent-a"))
        (tmp_path / "agent-b.yaml").write_text(VALID_YAML.replace("my-agent", "agent-b"))
        loader = ManifestLoader(str(tmp_path))
        result = loader.load_all()
        assert len(result) == 2
        assert "agent-a" in result
        assert "agent-b" in result

    def test_mixed_valid_and_invalid(self, tmp_path):
        (tmp_path / "good.yaml").write_text(VALID_YAML.replace("my-agent", "good"))
        (tmp_path / "bad.yaml").write_text(INVALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        result = loader.load_all()
        assert "good" in result
        assert len(result) == 1


class TestManifestLoaderGet:
    def test_get_existing(self, tmp_path):
        (tmp_path / "my-agent.yaml").write_text(VALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        loader.load_all()
        manifest = loader.get("my-agent")
        assert manifest is not None
        assert manifest.name == "my-agent"

    def test_get_nonexistent_returns_none(self, tmp_path):
        loader = ManifestLoader(str(tmp_path))
        assert loader.get("ghost-agent") is None

    def test_get_triggers_reload_when_file_changed(self, tmp_path):
        yaml_path = tmp_path / "my-agent.yaml"
        yaml_path.write_text(VALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        loader.load_all()

        # Modify the file and change mtime
        updated_yaml = VALID_YAML.replace('version: "1.0.0"', 'version: "2.0.0"')
        yaml_path.write_text(updated_yaml)
        # Force a different mtime
        new_mtime = yaml_path.stat().st_mtime + 1
        import os
        os.utime(yaml_path, (new_mtime, new_mtime))

        manifest = loader.get("my-agent")
        assert manifest is not None
        assert manifest.version == "2.0.0"

    def test_get_cached_when_mtime_unchanged(self, tmp_path):
        yaml_path = tmp_path / "my-agent.yaml"
        yaml_path.write_text(VALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        loader.load_all()

        # Get twice — should use cache (no file re-read triggered by mtime change)
        m1 = loader.get("my-agent")
        m2 = loader.get("my-agent")
        assert m1 is m2


class TestManifestLoaderGetMtime:
    def test_unknown_name_returns_zero(self, tmp_path):
        loader = ManifestLoader(str(tmp_path))
        assert loader.get_mtime("unknown") == 0.0

    def test_known_name_returns_float(self, tmp_path):
        (tmp_path / "my-agent.yaml").write_text(VALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        loader.load_all()
        mtime = loader.get_mtime("my-agent")
        assert isinstance(mtime, float)
        assert mtime > 0.0


class TestManifestLoaderAll:
    def test_all_delegates_to_load_all(self, tmp_path):
        (tmp_path / "my-agent.yaml").write_text(VALID_YAML)
        loader = ManifestLoader(str(tmp_path))
        result = loader.all()
        assert "my-agent" in result
