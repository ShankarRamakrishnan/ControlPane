"""API tests for manifest CRUD endpoints."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.core.manifest_loader import ManifestLoader
from gateway.core.runtime import RuntimeRegistry


EXTRA_MANIFEST_YAML = """\
name: extra-agent
version: "2.0.0"
description: "An extra agent"
model:
  provider: openai
  name: gpt-4o
  temperature: 0.0
tools: []
prompts:
  system: "Extra system prompt."
"""


class TestListManifests:
    def test_returns_200(self, client):
        response = client.get("/manifests")
        assert response.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/manifests").json()
        assert isinstance(data, list)

    def test_contains_loaded_manifest(self, client):
        data = client.get("/manifests").json()
        names = [m["name"] for m in data]
        assert "test-agent" in names

    def test_manifest_has_expected_fields(self, client):
        data = client.get("/manifests").json()
        assert len(data) > 0
        m = data[0]
        assert "name" in m
        assert "version" in m
        assert "description" in m
        assert "model" in m
        assert "tools" in m

    def test_empty_when_no_manifests(self, tmp_path):
        """An app with an empty manifests dir returns an empty list."""
        empty_dir = tmp_path / "empty_manifests"
        empty_dir.mkdir()

        from gateway.routers import manifests as manifests_router

        app = FastAPI()
        loader = ManifestLoader(str(empty_dir))
        loader.load_all()
        app.state.manifest_loader = loader
        app.state.runtime_registry = RuntimeRegistry()
        app.include_router(manifests_router.router)

        with TestClient(app) as c:
            response = c.get("/manifests")
        assert response.status_code == 200
        assert response.json() == []

    def test_multiple_manifests(self, tmp_path):
        """Returns all loaded manifests."""
        (tmp_path / "agent-a.yaml").write_text(
            EXTRA_MANIFEST_YAML.replace("extra-agent", "agent-a")
        )
        (tmp_path / "agent-b.yaml").write_text(
            EXTRA_MANIFEST_YAML.replace("extra-agent", "agent-b")
        )

        from gateway.routers import manifests as manifests_router

        app = FastAPI()
        loader = ManifestLoader(str(tmp_path))
        loader.load_all()
        app.state.manifest_loader = loader
        app.state.runtime_registry = RuntimeRegistry()
        app.include_router(manifests_router.router)

        with TestClient(app) as c:
            data = c.get("/manifests").json()
        names = {m["name"] for m in data}
        assert names == {"agent-a", "agent-b"}


class TestGetManifest:
    def test_returns_200_for_existing(self, client):
        response = client.get("/manifests/test-agent")
        assert response.status_code == 200

    def test_returns_manifest_data(self, client):
        data = client.get("/manifests/test-agent").json()
        assert data["name"] == "test-agent"
        assert data["version"] == "1.0.0"
        assert data["description"] == "Test agent for unit tests"

    def test_returns_404_for_unknown(self, client):
        response = client.get("/manifests/nonexistent-agent")
        assert response.status_code == 404

    def test_404_detail_message(self, client):
        response = client.get("/manifests/nonexistent-agent")
        detail = response.json()["detail"]
        assert "nonexistent-agent" in detail

    def test_model_config_present(self, client):
        data = client.get("/manifests/test-agent").json()
        assert "model" in data
        assert data["model"]["provider"] == "openai"

    def test_prompts_present(self, client):
        data = client.get("/manifests/test-agent").json()
        assert "prompts" in data
        assert "system" in data["prompts"]


NEW_MANIFEST_BODY = {
    "name": "new-agent",
    "version": "1.0.0",
    "description": "A brand new agent",
    "model": {"provider": "openai", "name": "gpt-4o", "temperature": 0.0},
    "tools": [],
    "prompts": {"system": "You are new."},
}


class TestCreateManifest:
    def test_returns_201(self, tmp_path):
        app, c = _make_app(tmp_path)
        with c:
            response = c.post("/manifests", json=NEW_MANIFEST_BODY)
        assert response.status_code == 201

    def test_returns_created_manifest(self, tmp_path):
        app, c = _make_app(tmp_path)
        with c:
            data = c.post("/manifests", json=NEW_MANIFEST_BODY).json()
        assert data["name"] == "new-agent"
        assert data["description"] == "A brand new agent"

    def test_writes_yaml_to_disk(self, tmp_path):
        app, c = _make_app(tmp_path)
        with c:
            c.post("/manifests", json=NEW_MANIFEST_BODY)
        assert (tmp_path / "new-agent.yaml").exists()

    def test_conflict_on_duplicate(self, tmp_path):
        app, c = _make_app(tmp_path)
        with c:
            c.post("/manifests", json=NEW_MANIFEST_BODY)
            response = c.post("/manifests", json=NEW_MANIFEST_BODY)
        assert response.status_code == 409

    def test_conflict_detail_includes_name(self, tmp_path):
        app, c = _make_app(tmp_path)
        with c:
            c.post("/manifests", json=NEW_MANIFEST_BODY)
            detail = c.post("/manifests", json=NEW_MANIFEST_BODY).json()["detail"]
        assert "new-agent" in detail


class TestUpdateManifest:
    def test_returns_200(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        updated = {**NEW_MANIFEST_BODY, "name": "seed-agent", "description": "Updated"}
        with c:
            response = c.put("/manifests/seed-agent", json=updated)
        assert response.status_code == 200

    def test_returns_updated_manifest(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        updated = {**NEW_MANIFEST_BODY, "name": "seed-agent", "description": "Updated desc"}
        with c:
            data = c.put("/manifests/seed-agent", json=updated).json()
        assert data["description"] == "Updated desc"

    def test_persists_to_disk(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        updated = {**NEW_MANIFEST_BODY, "name": "seed-agent", "description": "On disk"}
        with c:
            c.put("/manifests/seed-agent", json=updated)
        content = (tmp_path / "seed-agent.yaml").read_text()
        assert "On disk" in content

    def test_404_for_unknown(self, tmp_path):
        app, c = _make_app(tmp_path)
        updated = {**NEW_MANIFEST_BODY, "name": "ghost"}
        with c:
            response = c.put("/manifests/ghost", json=updated)
        assert response.status_code == 404

    def test_422_when_name_mismatch(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        mismatched = {**NEW_MANIFEST_BODY, "name": "wrong-name"}
        with c:
            response = c.put("/manifests/seed-agent", json=mismatched)
        assert response.status_code == 422


class TestDeleteManifest:
    def test_returns_204(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        with c:
            response = c.delete("/manifests/seed-agent")
        assert response.status_code == 204

    def test_removes_from_list(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        with c:
            c.delete("/manifests/seed-agent")
            data = c.get("/manifests").json()
        assert all(m["name"] != "seed-agent" for m in data)

    def test_removes_yaml_from_disk(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        with c:
            c.delete("/manifests/seed-agent")
        assert not (tmp_path / "seed-agent.yaml").exists()

    def test_404_for_unknown(self, tmp_path):
        app, c = _make_app(tmp_path)
        with c:
            response = c.delete("/manifests/ghost")
        assert response.status_code == 404

    def test_subsequent_get_returns_404(self, tmp_path):
        app, c = _make_app_with_agent(tmp_path)
        with c:
            c.delete("/manifests/seed-agent")
            response = c.get("/manifests/seed-agent")
        assert response.status_code == 404


# ── helpers ──────────────────────────────────────────────────────────────────

SEED_YAML = """\
name: seed-agent
version: "1.0.0"
description: "Seed agent"
model:
  provider: openai
  name: gpt-4o
  temperature: 0.0
tools: []
prompts:
  system: "You are a seed agent."
"""


def _make_app(tmp_path):
    from gateway.routers import manifests as manifests_router

    app = FastAPI()
    loader = ManifestLoader(str(tmp_path))
    loader.load_all()
    app.state.manifest_loader = loader
    app.state.runtime_registry = RuntimeRegistry()
    app.include_router(manifests_router.router)
    return app, TestClient(app)


def _make_app_with_agent(tmp_path):
    (tmp_path / "seed-agent.yaml").write_text(SEED_YAML)
    return _make_app(tmp_path)
