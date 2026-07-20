"""
API FastAPI pour l'agent IA SNOC.

Endpoints:
  POST /emails/simulate-inbox   -> traite tous les emails de app/data/sample_emails.json
  POST /emails/process          -> traite un email fourni dans le body
  GET  /audit                   -> historique des requêtes traitées
  GET  /kpi                     -> indicateurs clés (taux de résolution auto, etc.)
  GET  /outbox                  -> emails de réponse envoyés (mock)
  GET  /api/dashboard           -> métriques et historique prêts à alimenter le front-end
"""
import logging
import threading
import time
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse

from app.database import (
    fetch_all_audit,
    fetch_dashboard_data,
    fetch_kpis,
    init_db,
    get_setting,
    set_setting,
    claim_request,
    complete_request,
    fetch_events,
    fetch_outbox,
    update_escalation,
    process_pending_learning_jobs,
)
from app.integrations.email_mock import fetch_inbox
from app.workflow.graph import process_email

app = FastAPI(
    title="Agent IA SNOC - Support Automation",
    description="Prototype multi-agents (LangGraph) pour le traitement automatisé des demandes de support SNOC.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = PROJECT_ROOT / "snoc_automation_agents-main"


class EmailIn(BaseModel):
    id: str
    sender: str
    subject: str
    body: str
    attachments: List[str] = []


class EscalationUpdate(BaseModel):
    status: str
    assigned_to: str | None = None
    resolution_note: str | None = None


logger = logging.getLogger("snoc_worker")


def email_polling_worker():
    logger.info("Background email polling worker started.")
    while True:
        try:
            is_active = get_setting("agent_active", "true") == "true"
            if is_active:
                emails = fetch_inbox()
                for email in emails:
                    email_id = email.get("id")
                    if not email_id:
                        continue
                    if claim_request(email_id):
                        logger.info(f"Worker processing new email: {email_id}")
                        try:
                            process_email(email)
                            complete_request(email_id)
                        except Exception as e:
                            complete_request(email_id, str(e))
                            logger.error(f"Error processing email {email_id}: {e}")
        except Exception as e:
            logger.error(f"Error in background worker loop: {e}")
        time.sleep(10)


def learning_worker():
    """Consumes audit-derived learning observations outside customer request latency."""
    logger.info("Background learning worker started.")
    while True:
        try:
            processed = process_pending_learning_jobs()
            if processed:
                logger.info("Learning worker processed %s observation(s)", processed)
        except Exception as exc:
            logger.error("Learning worker error: %s", exc)
        time.sleep(10)


@app.on_event("startup")
def _startup():
    init_db()
    if not get_setting("agent_active"):
        set_setting("agent_active", "true")
    worker_thread = threading.Thread(target=email_polling_worker, daemon=True)
    worker_thread.start()
    threading.Thread(target=learning_worker, daemon=True).start()


@app.post("/emails/process")
def process_single_email(email: EmailIn):
    final_state = _process_new_email(email.model_dump())
    return _serialize_state(final_state)


@app.post("/api/process-email")
def process_dashboard_email(email: EmailIn):
    final_state = _process_new_email(email.model_dump())
    return {"status": "ok", "result": _serialize_state(final_state)}


@app.post("/emails/simulate-inbox")
@app.post("/api/simulate-inbox")
def simulate_inbox():
    results = []
    for email in fetch_inbox():
        if claim_request(email["id"]):
            try:
                final_state = process_email(email)
                complete_request(email["id"])
                results.append(_serialize_state(final_state))
            except Exception as exc:
                complete_request(email["id"], str(exc))
                raise HTTPException(status_code=500, detail=f"Failed to process {email['id']}") from exc
    return {"processed": len(results), "results": results}


@app.get("/audit")
def get_audit(limit: int = 50):
    return fetch_all_audit(limit=limit)


@app.get("/kpi")
def get_kpi():
    return fetch_kpis()


@app.get("/api/dashboard")
def get_dashboard():
    return fetch_dashboard_data(limit=40)


@app.get("/api/agent-status")
def get_agent_status():
    return {"agent_active": get_setting("agent_active", "true") == "true"}


@app.post("/api/agent-toggle")
def toggle_agent_status():
    current = get_setting("agent_active", "true") == "true"
    new_state = "false" if current else "true"
    set_setting("agent_active", new_state)
    return {"agent_active": new_state == "true"}


@app.get("/outbox")
def get_outbox_route():
    return fetch_outbox()


@app.get("/api/requests/{request_id}/events")
def get_request_events(request_id: str):
    return fetch_events(request_id)


@app.patch("/api/escalations/{request_id}")
def patch_escalation(request_id: str, update: EscalationUpdate):
    if not update_escalation(request_id, update.status, update.assigned_to, update.resolution_note):
        raise HTTPException(status_code=404, detail="Escalation not found")
    return {"request_id": request_id, "status": update.status}


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/style.css")
def style_css():
    return FileResponse(FRONTEND_DIR / "style.css")


@app.get("/app.js")
def app_js():
    return FileResponse(FRONTEND_DIR / "app.js")


if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


def _serialize_state(state: dict) -> dict:
    return {
        "request_id": state.get("request_id"),
        "sender": state.get("sender"),
        "rejected": state.get("rejected", False),
        "intent": state.get("intent"),
        "confidence": state.get("intent_confidence"),
        "language": state.get("detected_language"),
        "entities": state.get("entities"),
        "decision": state.get("decision"),
        "decision_reason": state.get("decision_reason"),
        "verification_passed": state.get("verification_passed"),
        "execution_status": state.get("execution_status"),
        "execution_details": state.get("execution_details"),
        "reply_text": state.get("reply_text"),
        "trace": state.get("trace"),
    }


def _process_new_email(email: dict) -> dict:
    """Reserve an email id before running side-effecting agent actions."""
    if not claim_request(email["id"]):
        raise HTTPException(status_code=409, detail="This email has already been accepted for processing")
    try:
        state = process_email(email)
        complete_request(email["id"])
        return state
    except Exception as exc:
        complete_request(email["id"], str(exc))
        raise
