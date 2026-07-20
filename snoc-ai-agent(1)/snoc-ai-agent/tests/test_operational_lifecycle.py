"""Regression coverage for durable operational workflow behaviour."""
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_conn, process_pending_learning_jobs


def test_rejected_email_is_audited_and_reply_is_persisted():
    client = TestClient(app)
    payload = {
        "id": "unauthorized-audit-1",
        "sender": "unknown@example.net",
        "subject": "Unlock request",
        "body": "Please unlock PDV-45210",
    }

    response = client.post("/emails/process", json=payload)
    assert response.status_code == 200
    assert response.json()["rejected"] is True

    audit = client.get("/audit").json()
    assert any(row["request_id"] == payload["id"] and row["request_status"] == "Rejected" for row in audit)
    outbox = client.get("/outbox").json()
    assert any(row["request_id"] == payload["id"] for row in outbox)


def test_api_rejects_duplicate_message_before_side_effects():
    client = TestClient(app)
    payload = {
        "id": "idempotency-1",
        "sender": "animateur.zone1@company.com",
        "subject": "Unlock request",
        "body": "Please unlock PDV-45210",
    }

    assert client.post("/emails/process", json=payload).status_code == 200
    duplicate = client.post("/emails/process", json=payload)
    assert duplicate.status_code == 409


def test_learning_is_queued_then_processed_outside_request_path():
    client = TestClient(app)
    payload = {
        "id": "learning-async-1",
        "sender": "animateur.zone1@company.com",
        "subject": "Unlock request",
        "body": "Please unlock PDV-45210",
    }
    assert client.post("/emails/process", json=payload).status_code == 200

    with get_conn() as conn:
        assert conn.execute("SELECT status FROM learning_jobs WHERE request_id = ?", (payload["id"],)).fetchone()["status"] == "pending"
    assert process_pending_learning_jobs() == 1
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM knowledge_base WHERE request_id = ?", (payload["id"],)).fetchone()["c"] == 1
