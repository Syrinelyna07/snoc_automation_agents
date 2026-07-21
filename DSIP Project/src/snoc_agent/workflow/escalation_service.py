"""Structured human-escalation persistence."""

from __future__ import annotations

import hashlib
import json
from email.utils import make_msgid
from typing import Any

from sqlalchemy.orm import Session

from snoc_agent.db.models import (
    BusinessRequest,
    EmailMessage,
    Escalation,
    OutboxMessage,
)
from snoc_agent.domain.enums import Direction, OutboxStatus, ProcessingStatus
from snoc_agent.domain.value_objects import reject_header_injection
from snoc_agent.mail.headers import build_references, normalize_message_id


def create_escalation(
    session: Session,
    *,
    email: EmailMessage,
    request: BusinessRequest | None,
    recipient: str,
    reason_code: str,
    summary: str,
    evidence: dict[str, Any],
    queue_email: bool = False,
    sender_address: str | None = None,
) -> Escalation:
    latest_text = email.latest_user_message[:4000]
    stored_operations = []
    if request:
        stored_operations = [
            {
                "operation_id": str(operation.id),
                "action": operation.action,
                "status": operation.status,
                "pdv_code": operation.pdv_code,
                "phone": operation.phone,
                "additional_payload": operation.additional_payload,
                "missing_fields": operation.missing_fields,
                "evidence": operation.evidence,
                "field_provenance": operation.field_provenance,
                "contradiction_data": operation.contradiction_data,
                "current_revision": operation.current_revision,
                "final_decision": operation.final_decision,
            }
            for operation in request.operations
        ]
    structured_evidence = {
        **evidence,
        "email_context": {
            "internal_email_id": str(email.id),
            "sender": email.sender,
            "subject": email.subject,
            "message_id": email.rfc_message_id,
            "in_reply_to": email.in_reply_to,
            "references": email.references_json,
            "latest_user_message": latest_text,
            "latest_user_message_truncated": len(email.latest_user_message) > len(latest_text),
            "raw_eml_path": email.raw_eml_path,
        },
        "stored_request_state": {
            "request_id": str(request.id) if request else None,
            "public_reference": request.public_reference if request else None,
            "request_status": request.status if request else None,
            "operations": stored_operations,
        },
    }
    escalation = Escalation(
        request_id=request.id if request else None,
        email_message_id=email.id,
        recipient=recipient,
        reason_code=reason_code,
        summary=summary,
        evidence=structured_evidence,
    )
    session.add(escalation)
    session.flush()
    if request:
        request.escalation_reason = summary
    if queue_email:
        if not sender_address:
            raise ValueError("sender_address is required when queuing an escalation email")
        sender_address = reject_header_injection(sender_address)
        recipient = reject_header_injection(recipient)
        reference = request.public_reference if request else "SNOC-NON-CORRELATED"
        subject = reject_header_injection(f"[{reference}] Escalade pour contrôle humain")
        body = "\n".join(
            [
                "Escalade structurée du service SNOC",
                "",
                f"Référence : {reference}",
                f"Email interne : {email.id}",
                f"Expéditeur : {email.sender}",
                f"Objet : {email.subject}",
                f"Message-ID : {email.rfc_message_id or '(absent)'}",
                f"In-Reply-To : {email.in_reply_to or '(absent)'}",
                f"References : {' '.join(email.references_json) or '(absentes)'}",
                f"Motif : {reason_code}",
                f"Résumé : {summary}",
                "",
                "Dernier contenu utilisateur pertinent :",
                latest_text or "(vide)",
                "",
                "Éléments de décision :",
                json.dumps(structured_evidence, ensure_ascii=False, indent=2, default=str),
                "",
                "Action recommandée : vérifier les éléments ci-dessus et traiter manuellement.",
            ]
        )
        domain = sender_address.rsplit("@", 1)[-1] if "@" in sender_address else None
        message_id = make_msgid(domain=domain)
        references = build_references(email.references_json, email.rfc_message_id)
        headers = {
            "Message-ID": message_id,
            "In-Reply-To": normalize_message_id(email.rfc_message_id) or "",
            "References": " ".join(references),
            "X-SNOC-Escalation-ID": str(escalation.id),
        }
        if request:
            headers["X-SNOC-Request-ID"] = request.public_reference
        outbound = EmailMessage(
            conversation_id=email.conversation_id,
            direction=Direction.OUTBOUND.value,
            rfc_message_id=message_id,
            normalized_message_id=normalize_message_id(message_id),
            in_reply_to=headers["In-Reply-To"] or None,
            references_json=references,
            sender=sender_address,
            recipients_json=[recipient],
            cc_json=[],
            subject=subject,
            normalized_subject=email.normalized_subject,
            raw_text=body,
            latest_user_message=body,
            quoted_text="",
            signature_text="",
            raw_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            mime_type="text/plain",
            attachment_metadata=[],
            flags_json=[],
            processing_status=ProcessingStatus.STORED.value,
            parsing_warnings=[],
            correlation_details={},
        )
        session.add(outbound)
        session.flush()
        session.add(
            OutboxMessage(
                related_request_id=request.id if request else None,
                outbound_email_id=outbound.id,
                recipient=recipient,
                subject=subject,
                body=body,
                headers=headers,
                status=OutboxStatus.PENDING.value,
            )
        )
    return escalation
