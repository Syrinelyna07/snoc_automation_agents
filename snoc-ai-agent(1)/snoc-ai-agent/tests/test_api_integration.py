import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_dashboard_endpoint_returns_live_metrics():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert "stats" in body
    assert "requests" in body
    assert "alerts" in body
    assert body["stats"]["total_requests"] >= 0


def test_agent_status_and_toggle_endpoints():
    response = client.get("/api/agent-status")
    assert response.status_code == 200
    initial_status = response.json()["agent_active"]

    response = client.post("/api/agent-toggle")
    assert response.status_code == 200
    new_status = response.json()["agent_active"]
    assert new_status == (not initial_status)

    response = client.get("/api/agent-status")
    assert response.status_code == 200
    assert response.json()["agent_active"] == new_status

    response = client.post("/api/agent-toggle")
    assert response.status_code == 200
    assert response.json()["agent_active"] == initial_status
