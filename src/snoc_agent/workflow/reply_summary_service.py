"""One completion/terminal summary per request."""

from __future__ import annotations

from sqlalchemy.orm import Session

from snoc_agent.db.models import BusinessRequest, EmailMessage, Operation
from snoc_agent.domain.enums import OperationStatus
from snoc_agent.mail.markers import completion_marker
from snoc_agent.mail.templates import OperationMailView, completion_email
from snoc_agent.workflow.reply_service import create_outbound_message

STATUS_LABELS = {
    OperationStatus.COMPLETED.value: "terminé",
    OperationStatus.ESCALATED.value: "transmis à un agent humain",
    OperationStatus.FAILED.value: "échec — transmis à un agent humain",
    OperationStatus.CANCELLED.value: "annulé",
    OperationStatus.NEEDS_INFORMATION.value: "informations manquantes",
}


def ensure_terminal_summary(
    session: Session,
    *,
    request: BusinessRequest,
    source_email: EmailMessage,
    operations: list[Operation],
    sender_address: str,
    recipient: str,
) -> bool:
    if request.latest_completion_marker:
        return False
    terminal = {
        OperationStatus.COMPLETED.value,
        OperationStatus.ESCALATED.value,
        OperationStatus.FAILED.value,
        OperationStatus.CANCELLED.value,
    }
    if not operations or any(operation.status not in terminal for operation in operations):
        return False
    views = [
        OperationMailView(
            sequence_number=operation.sequence_number,
            action=operation.action,
            pdv_code=operation.pdv_code,
            status_label=STATUS_LABELS.get(operation.status, operation.status),
        )
        for operation in operations
    ]
    subject, body = completion_email(request.public_reference, views)
    create_outbound_message(
        session,
        request=request,
        source_email=source_email,
        sender=sender_address,
        recipient=recipient,
        subject=subject,
        body=body,
        extra_headers={
            "X-SNOC-Operation-IDs": ",".join(str(operation.id) for operation in operations)
        },
    )
    request.latest_completion_marker = completion_marker(request.public_reference)
    return True
