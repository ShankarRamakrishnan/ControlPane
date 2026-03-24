"""API tests for GET /health."""
import pytest
from unittest.mock import patch


class TestHealthEndpoint:
    def test_returns_ok_status(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_tracing_false_when_not_configured(self, client):
        with patch("gateway.routers.health.is_tracing_enabled", return_value=False):
            response = client.get("/health")
        assert response.json()["tracing"] is False

    def test_tracing_true_when_configured(self, client):
        with patch("gateway.routers.health.is_tracing_enabled", return_value=True):
            response = client.get("/health")
        assert response.json()["tracing"] is True

    def test_response_has_required_keys(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "tracing" in data

    def test_content_type_is_json(self, client):
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]
