"""
Couche de persistance pour le journal d'audit (Audit Agent).
Utilise SQLite pour le prototype. Le schéma est compatible PostgreSQL (cf. tech stack cible)
sans modification autre que le driver de connexion.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "audit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    sender TEXT NOT NULL,
    subject TEXT,
    body_text TEXT,
    cleaned_text TEXT,
    intent TEXT,
    confidence REAL,
    decision TEXT,
    execution_status TEXT,
    execution_details TEXT,
    verification_passed INTEGER,
    verification_issues TEXT,
    reply_text TEXT,
    reply_subject TEXT,
    detected_language TEXT,
    entities_json TEXT,
    zone TEXT,
    request_type TEXT,
    request_status TEXT,
    source TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    intent TEXT,
    was_correct INTEGER,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS request_jobs (
    request_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    created_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS escalation_cases (
    request_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('open', 'assigned', 'resolved', 'closed')),
    assigned_to TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    intent TEXT,
    was_correct INTEGER NOT NULL,
    note TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed')) DEFAULT 'pending',
    created_at TEXT NOT NULL,
    processed_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

MIGRATIONS = [
    ("body_text", "TEXT"),
    ("cleaned_text", "TEXT"),
    ("verification_issues", "TEXT"),
    ("reply_subject", "TEXT"),
    ("detected_language", "TEXT"),
    ("entities_json", "TEXT"),
    ("zone", "TEXT"),
    ("request_type", "TEXT"),
    ("request_status", "TEXT"),
    ("source", "TEXT"),
    ("metadata_json", "TEXT"),
]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    existing_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(audit_log)").fetchall()
    }
    for column_name, column_type in MIGRATIONS:
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE audit_log ADD COLUMN {column_name} {column_type}")
    # Fresh databases enforce this in the table definition.  Older demo databases
    # may contain duplicate history, which must not make startup fail or be silently
    # deleted; request_jobs still supplies the operational idempotency guarantee.
    has_historic_duplicates = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM audit_log GROUP BY request_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    if not has_historic_duplicates:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_request_id ON audit_log(request_id)")
    else:
        conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_request_id ON audit_log(request_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_created_at ON audit_log(created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_status ON audit_log(request_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_events_request_id ON workflow_events(request_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_outbox_request_id ON outbox(request_id, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_learning_jobs_pending ON learning_jobs(status, id)")


def init_db():
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        _ensure_schema(conn)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_request(request_id: str) -> bool:
    """Atomically claim an inbound message before it can cause side effects."""
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO request_jobs (request_id, status, created_at) VALUES (?, 'processing', ?)",
            (request_id, _now()),
        )
        return cursor.rowcount == 1


def complete_request(request_id: str, error: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE request_jobs SET status = ?, completed_at = ?, error = ? WHERE request_id = ?",
            ("failed" if error else "completed", _now(), error, request_id),
        )


def record_event(request_id: str, event_type: str, details: dict | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO workflow_events (request_id, event_type, details_json, created_at) VALUES (?, ?, ?, ?)",
            (request_id, event_type, json.dumps(details or {}, ensure_ascii=False), _now()),
        )


def record_outbox(request_id: str, recipient: str, subject: str, body: str, delivery_status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO outbox (request_id, recipient, subject, body, delivery_status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (request_id, recipient, subject, body, delivery_status, _now()),
        )


def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )


def _derive_request_status(state: dict) -> str:
    if state.get("rejected"):
        return "Rejected"
    decision = (state.get("decision") or "").lower()
    if decision == "auto_execute":
        return "Success" if state.get("execution_status") == "success" else "Processing"
    if decision == "escalate":
        return "Escalated"
    if decision == "clarify":
        return "Processing"
    if decision == "reject":
        return "Rejected"
    return "Processing"


def _derive_request_type(state: dict) -> str:
    intent = (state.get("request_type") or state.get("intent") or "unknown").lower()
    if intent in {"unlock_account", "reactivate_account"}:
        return "Account Access"
    if intent in {"create_pdv_account", "create_vpn_account"}:
        return "Service Provisioning"
    if intent == "reset_password":
        return "Password Reset"
    if intent == "update_otp_phone":
        return "OTP Update"
    return state.get("request_type") or (state.get("intent") or "unknown").replace("_", " ").title()


def _extract_zone(state: dict) -> str | None:
    sender_profile = state.get("sender_profile") or {}
    zone = sender_profile.get("zone")
    if zone:
        return zone
    entities = state.get("entities") or {}
    return entities.get("zone")


def insert_audit(state: dict) -> str:
    request_id = state["request_id"]
    entities = state.get("entities") or {}
    metadata = {
        "rejected": bool(state.get("rejected", False)),
        "rejection_reason": state.get("rejection_reason"),
        "verification_issues": state.get("verification_issues", []),
        "sender_profile": state.get("sender_profile"),
        "execution_details": state.get("execution_details", {}),
    }
    request_status = _derive_request_status(state)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO audit_log
               (request_id, sender, subject, body_text, cleaned_text, intent, confidence, decision,
                execution_status, execution_details, verification_passed, verification_issues,
                reply_text, reply_subject, detected_language, entities_json, zone,
                request_type, request_status, source, metadata_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                request_id,
                state.get("sender"),
                state.get("subject"),
                state.get("body"),
                state.get("cleaned_text"),
                state.get("intent"),
                state.get("intent_confidence"),
                state.get("decision"),
                state.get("execution_status"),
                json.dumps(state.get("execution_details", {}), ensure_ascii=False),
                int(bool(state.get("verification_passed", False))),
                json.dumps(state.get("verification_issues", []), ensure_ascii=False),
                state.get("reply_text"),
                state.get("reply_subject") or (f"RE: {state.get('subject')}" if state.get("subject") else None),
                state.get("detected_language"),
                json.dumps(entities, ensure_ascii=False),
                _extract_zone(state),
                _derive_request_type(state),
                request_status,
                "email",
                json.dumps(metadata, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        if request_status == "Escalated":
            now = _now()
            conn.execute(
                """INSERT OR IGNORE INTO escalation_cases
                   (request_id, status, created_at, updated_at) VALUES (?, 'open', ?, ?)""",
                (request_id, now, now),
            )
    return request_id


def insert_learning_note(request_id: str, intent: str, was_correct: bool, note: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO knowledge_base (request_id, intent, was_correct, note, created_at)
               VALUES (?,?,?,?,?)""",
            (request_id, intent, int(was_correct), note, datetime.now(timezone.utc).isoformat()),
        )


def enqueue_learning_job(state: dict) -> None:
    """Queue learning work after the request is durably audited, never inline."""
    was_auto_resolved = state.get("decision") == "auto_execute" and state.get("execution_status") == "success"
    note = (
        f"intent={state.get('intent')} confidence={state.get('intent_confidence')} "
        f"decision={state.get('decision')} execution={state.get('execution_status')} "
        f"language={state.get('detected_language')}"
    )
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO learning_jobs
               (request_id, intent, was_correct, note, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (state["request_id"], state.get("intent", "unknown"), int(was_auto_resolved), note, _now()),
        )


def process_pending_learning_jobs(limit: int = 50) -> int:
    """Persist queued learning observations; model retraining remains an offline concern."""
    with get_conn() as conn:
        jobs = conn.execute(
            "SELECT * FROM learning_jobs WHERE status = 'pending' ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
        for job in jobs:
            try:
                conn.execute(
                    "INSERT INTO knowledge_base (request_id, intent, was_correct, note, created_at) VALUES (?, ?, ?, ?, ?)",
                    (job["request_id"], job["intent"], job["was_correct"], job["note"], _now()),
                )
                conn.execute(
                    "UPDATE learning_jobs SET status = 'completed', processed_at = ? WHERE id = ?",
                    (_now(), job["id"]),
                )
            except Exception as exc:
                conn.execute(
                    "UPDATE learning_jobs SET status = 'failed', error = ? WHERE id = ?",
                    (str(exc), job["id"]),
                )
        return len(jobs)


def fetch_all_audit(limit: int = 100):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        records = []
        for row in rows:
            record = dict(row)
            record["entities"] = json.loads(record.get("entities_json") or "{}")
            record["metadata"] = json.loads(record.get("metadata_json") or "{}")
            record["verification_issues"] = json.loads(record.get("verification_issues") or "[]")
            record["execution_details"] = json.loads(record.get("execution_details") or "{}")
            record["request_type"] = _derive_request_type(record)
            records.append(record)
        return records


def fetch_kpis():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
        auto = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE decision='auto_execute'"
        ).fetchone()["c"]
        escalated = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE request_status='Escalated'"
        ).fetchone()["c"]
        rejected = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE request_status='Rejected'"
        ).fetchone()["c"]
        success = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE execution_status='success'"
        ).fetchone()["c"]
        avg_confidence = conn.execute(
            "SELECT AVG(confidence) c FROM audit_log"
        ).fetchone()["c"] or 0.0
        pending = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE request_status='Processing'"
        ).fetchone()["c"]
        failed = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE execution_status='failed'"
        ).fetchone()["c"]
        unauthorized = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE request_status='Rejected'"
        ).fetchone()["c"]
        missing_entities = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE decision='clarify'"
        ).fetchone()["c"]
        low_confidence = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE confidence < 0.85"
        ).fetchone()["c"]
        return {
            "total_requests": total,
            "auto_executed": auto,
            "escalated": escalated,
            "rejected": rejected,
            "successful_executions": success,
            "pending_requests": pending,
            "in_progress": pending,
            "failed": failed,
            "average_confidence": round(avg_confidence * 100, 1) if avg_confidence <= 1 else round(avg_confidence, 1),
            "auto_resolution_rate": round(auto / total, 3) if total else 0.0,
            "low_confidence": low_confidence,
            "missing_entities": missing_entities,
            "unauthorized": unauthorized,
        }


def fetch_outbox(limit: int = 100):
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM outbox ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


def fetch_events(request_id: str):
    with get_conn() as conn:
        events = []
        for row in conn.execute(
            "SELECT * FROM workflow_events WHERE request_id = ? ORDER BY id", (request_id,)
        ).fetchall():
            event = dict(row)
            event["details"] = json.loads(event.pop("details_json") or "{}")
            events.append(event)
        return events


def update_escalation(request_id: str, status: str, assigned_to: str | None = None, resolution_note: str | None = None):
    if status not in {"open", "assigned", "resolved", "closed"}:
        raise ValueError("Invalid escalation status")
    with get_conn() as conn:
        cursor = conn.execute(
            """UPDATE escalation_cases
               SET status = ?, assigned_to = COALESCE(?, assigned_to),
                   resolution_note = COALESCE(?, resolution_note), updated_at = ?
               WHERE request_id = ?""",
            (status, assigned_to, resolution_note, _now(), request_id),
        )
        return cursor.rowcount == 1


def fetch_dashboard_data(limit: int = 40):
    requests = fetch_all_audit(limit=limit)
    stats = fetch_kpis()
    alerts = []
    for request in requests[:8]:
        status = request.get("request_status")
        if status == "Escalated":
            alerts.append(
                {
                    "id": f"A{len(alerts) + 1}",
                    "severity": "warning",
                    "message": f"{request.get('intent') or 'Request'} required supervisor review",
                    "time": request.get("created_at", ""),
                    "region": request.get("zone") or "All Zones",
                    "status": "Active",
                }
            )
    if not alerts:
        alerts.append(
            {
                "id": "A1",
                "severity": "info",
                "message": "Agent pipeline is healthy and awaiting new requests",
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "region": "All Zones",
                "status": "Active",
            }
        )
    return {
        "stats": stats,
        "requests": requests,
        "alerts": alerts,
        "agent_active": get_setting("agent_active", "true") == "true",
    }
