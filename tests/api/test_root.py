"""API tests for GET /."""


class TestRootEndpoint:
    def test_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_contains_name(self, client):
        data = client.get("/").json()
        assert data["name"] == "ControlPane"

    def test_contains_version(self, client):
        data = client.get("/").json()
        assert "version" in data

    def test_contains_docs_path(self, client):
        data = client.get("/").json()
        assert data["docs"] == "/docs"

    def test_contains_agents_and_manifests_paths(self, client):
        data = client.get("/").json()
        assert data["agents"] == "/agents"
        assert data["manifests"] == "/manifests"

    def test_content_type_is_json(self, client):
        response = client.get("/")
        assert "application/json" in response.headers["content-type"]
