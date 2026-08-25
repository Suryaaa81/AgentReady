"""Tests for GET /health endpoint."""

from __future__ import annotations


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_payload_structure(client):
    data = client.get("/health").json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "timestamp" in data
    assert "version" in data
    assert "services" in data
    assert "database" in data["services"]


def test_health_db_ok(client):
    """With in-memory SQLite the DB should always report ok."""
    data = client.get("/health").json()
    assert data["services"]["database"] == "ok"
    assert data["status"] == "ok"
