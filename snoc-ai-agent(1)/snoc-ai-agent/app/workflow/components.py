"""Consolidated operational workflow components."""
import json
import re

from app.config import CONFIDENCE_THRESHOLD_AUTO_EXECUTE, CONFIDENCE_THRESHOLD_CLARIFY, WHITELIST_PATH
from app.database import enqueue_learning_job, insert_audit, record_event, record_outbox
from app.integrations.email_mock import send_reply
from app.integrations.snoc_mock_api import ACTIONS, SNOCApiError, get_account
from app.llm.llm_client import classify_intent_and_extract
from app.models import WorkflowState

with open(WHITELIST_PATH, encoding="utf-8") as whitelist_file:
    WHITELIST = {entry["email"].lower(): entry for entry in json.load(whitelist_file)["authorized_senders"]}

REQUIRED_ENTITIES = {
    "unlock_account": ["pdv_code"], "reset_password": ["pdv_code"],
    "reactivate_account": ["pdv_code"], "update_otp_phone": ["pdv_code", "phone_number"],
    "create_pdv_account": ["partner_name", "phone_number"], "create_vpn_account": ["employee_id"],
}
ACTION_PARAMS = {
    "unlock_account": lambda e: {"pdv_code": e.get("pdv_code")},
    "reset_password": lambda e: {"pdv_code": e.get("pdv_code")},
    "reactivate_account": lambda e: {"pdv_code": e.get("pdv_code")},
    "update_otp_phone": lambda e: {"pdv_code": e.get("pdv_code"), "new_phone": e.get("phone_number")},
    "create_pdv_account": lambda e: {"partner_name": e.get("partner_name"), "phone_number": e.get("phone_number"), "zone": e.get("zone", "N/A")},
    "create_vpn_account": lambda e: {"employee_name": e.get("employee_name", "N/A"), "employee_id": e.get("employee_id")},
}
SIGNATURE_MARKERS = ("cordialement", "regards", "thanks", "merci d'avance", "best regards", "tel:", "tél:", "sent from my", "envoyé depuis")
PHONE_RE = re.compile(r"^0\d{9}$")
REPLY_TEMPLATES = {
    "rejected": {"fr": "Bonjour,\n\nVotre demande n'a pas pu être traitée car votre adresse n'est pas autorisée à utiliser ce service automatisé. Merci de contacter le Helpdesk.\n\nCordialement,\nAgent Support SNOC", "en": "Hello,\n\nYour request could not be processed because your email address is not authorized to use this automated service. Please contact the Helpdesk.\n\nBest regards,\nSNOC Support Agent"},
    "success": {"fr": "Bonjour,\n\nVotre demande a été traitée avec succès.\nDétails: {details}\n\nCordialement,\nAgent Support SNOC", "en": "Hello,\n\nYour request has been processed successfully.\nDetails: {details}\n\nBest regards,\nSNOC Support Agent"},
    "failed": {"fr": "Bonjour,\n\nVotre demande n'a pas pu être exécutée automatiquement ({error}). Elle a été transmise à notre équipe pour traitement manuel.\n\nCordialement,\nAgent Support SNOC", "en": "Hello,\n\nYour request could not be executed automatically ({error}). It has been forwarded to our team for manual handling.\n\nBest regards,\nSNOC Support Agent"},
    "clarify": {"fr": "Bonjour,\n\nAfin de traiter votre demande, merci de nous fournir les informations suivantes : {reason}\n\nCordialement,\nAgent Support SNOC", "en": "Hello,\n\nTo process your request, please provide the following information: {reason}\n\nBest regards,\nSNOC Support Agent"},
    "escalate": {"fr": "Bonjour,\n\nVotre demande a été transmise à un agent humain de l'équipe Digital Technical Support pour traitement ({reason}). Vous recevrez une réponse sous peu.\n\nCordialement,\nAgent Support SNOC", "en": "Hello,\n\nYour request has been forwarded to a human agent from the Digital Technical Support team ({reason}). You will receive a response shortly.\n\nBest regards,\nSNOC Support Agent"},
}


def ingress(email: dict) -> WorkflowState:
    state: WorkflowState = {"request_id": email["id"], "sender": email["sender"], "subject": email["subject"], "body": email["body"], "attachments": email.get("attachments", []), "trace": [f"[Ingress] Request {email['id']} received"]}
    record_event(state["request_id"], "received", {"sender": state["sender"]})
    return state


def security(state: WorkflowState) -> WorkflowState:
    profile = WHITELIST.get(state["sender"].lower())
    state["is_whitelisted"] = profile is not None
    state["sender_profile"] = profile
    state["rejected"] = profile is None
    if profile is None:
        state["rejection_reason"] = "Sender is not present in the authorized whitelist."
    state["trace"].append("[Security] authorized" if profile else "[Security] rejected sender")
    record_event(
        state["request_id"], "security_checked",
        {"authorized": state.get("is_whitelisted", False), "reason": state.get("rejection_reason")},
    )
    return state


def nlu(state: WorkflowState) -> WorkflowState:
    lines = []
    for line in f"{state['subject']}\n{state['body']}".splitlines():
        if any(line.strip().lower().startswith(marker) for marker in SIGNATURE_MARKERS): break
        lines.append(line)
    state["cleaned_text"] = re.sub(r"\s+", " ", "\n".join(lines)).strip()
    state["normalized_prompt"] = state["cleaned_text"]
    result = classify_intent_and_extract(state["normalized_prompt"])
    state.update(intent=result["intent"], intent_confidence=result["confidence"], detected_language=result["language"], entities=result["entities"])
    state["trace"].append(f"[NLU] intent={result['intent']} confidence={result['confidence']}")
    record_event(
        state["request_id"], "nlu_completed",
        {"intent": state.get("intent"), "confidence": state.get("intent_confidence"), "entities": state.get("entities", {})},
    )
    return state


def policy(state: WorkflowState) -> WorkflowState:
    intent, confidence, entities = state["intent"], state["intent_confidence"], state.get("entities", {})
    missing = [key for key in REQUIRED_ENTITIES.get(intent, []) if not entities.get(key)]
    if intent == "unknown":
        state["decision"], state["decision_reason"] = "escalate", "Unrecognized intent."
    elif missing:
        state["decision"], state["decision_reason"] = "clarify", f"Missing information: {', '.join(missing)}."
    elif confidence >= CONFIDENCE_THRESHOLD_AUTO_EXECUTE:
        state["decision"], state["decision_reason"] = "auto_execute", f"High confidence ({confidence}) and complete entities."
    elif confidence >= CONFIDENCE_THRESHOLD_CLARIFY:
        state["decision"], state["decision_reason"] = "clarify", f"Moderate confidence ({confidence}), confirmation required."
    else:
        state["decision"], state["decision_reason"] = "escalate", f"Low confidence ({confidence})."
    issues = []
    pdv = entities.get("pdv_code")
    if state["decision"] == "auto_execute" and intent in {"unlock_account", "reset_password", "reactivate_account", "update_otp_phone"} and pdv and get_account(pdv) is None: issues.append(f"Account {pdv} does not exist in SNOC.")
    if state["decision"] == "auto_execute" and entities.get("phone_number") and not PHONE_RE.match(entities["phone_number"]): issues.append("Invalid phone number format.")
    state["verification_issues"], state["verification_passed"] = issues, not issues
    if issues:
        state["decision"], state["decision_reason"] = "escalate", "Verification failed: " + "; ".join(issues)
    state["trace"].append(f"[Policy] {state['decision']}")
    record_event(
        state["request_id"], "policy_decided",
        {"decision": state.get("decision"), "reason": state.get("decision_reason"), "verification_issues": state.get("verification_issues", [])},
    )
    return state


def fulfilment(state: WorkflowState) -> WorkflowState:
    # A rejected request has no business action, but still receives the same
    # controlled customer reply and durable delivery record.
    if not state.get("rejected"):
        if state["decision"] != "auto_execute":
            state["execution_status"], state["execution_details"] = "skipped", {"reason": f"decision={state['decision']}"}
        else:
            action, params = ACTIONS.get(state["intent"]), ACTION_PARAMS.get(state["intent"])
            if not action or not params:
                state["execution_status"], state["execution_details"] = "failed", {"error": "No action mapping for intent"}
            else:
                try:
                    state["execution_status"], state["execution_details"] = "success", action(**params(state.get("entities", {})))
                except SNOCApiError as exc:
                    state["execution_status"], state["execution_details"] = "failed", {"error": str(exc)}
                except Exception as exc:
                    state["execution_status"], state["execution_details"] = "failed", {"error": f"Unexpected error: {exc}"}
        record_event(
            state["request_id"], "execution_completed",
            {"status": state.get("execution_status"), "details": state.get("execution_details", {})},
        )
    lang = "en" if state.get("detected_language") == "en" else "fr"
    if state.get("rejected"): template, values = "rejected", {}
    elif state["decision"] == "auto_execute" and state["execution_status"] == "success": template, values = "success", {"details": state["execution_details"]}
    elif state["decision"] == "auto_execute": template, values = "failed", {"error": state["execution_details"].get("error", "unknown error")}
    elif state["decision"] == "clarify": template, values = "clarify", {"reason": state["decision_reason"]}
    else: template, values = "escalate", {"reason": state["decision_reason"]}
    body, subject = REPLY_TEMPLATES[template][lang].format(**values), f"RE: {state['subject']}"
    delivery = send_reply(state["sender"], subject, body)
    record_outbox(state["request_id"], state["sender"], subject, body, delivery.get("delivery_status", "sent"))
    record_event(state["request_id"], "reply_sent", {"recipient": state["sender"], "delivery_status": delivery.get("delivery_status", "sent")})
    state["reply_text"] = body
    return state


def audit_and_enqueue_learning(state: WorkflowState) -> WorkflowState:
    state["audit_id"] = insert_audit(state)
    record_event(state["request_id"], "audit_recorded", {"decision": state.get("decision"), "execution_status": state.get("execution_status")})
    enqueue_learning_job(state)
    record_event(state["request_id"], "learning_queued")
    return state
