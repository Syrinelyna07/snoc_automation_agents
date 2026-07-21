"""Deterministic, structured French email templates."""

from __future__ import annotations

from dataclasses import dataclass

from snoc_agent.domain.enums import OperationAction
from snoc_agent.mail.markers import completion_marker

ACTION_LABELS = {
    OperationAction.VPN_ACCESS.value: "accès VPN/SNOC",
    OperationAction.OTP_NUMBER_CHANGE.value: "changement du numéro OTP",
    OperationAction.ACCOUNT_UNBLOCK.value: "déblocage du compte",
    OperationAction.PASSWORD_RESET.value: "réinitialisation du mot de passe",
    OperationAction.UNKNOWN.value: "opération non déterminée",
}
FIELD_LABELS = {
    "pdv_code": "code PDV (8 chiffres)",
    "phone": "numéro de téléphone",
    "new_phone": "nouveau numéro OTP",
}


@dataclass(frozen=True, slots=True)
class OperationMailView:
    sequence_number: int
    action: str
    pdv_code: str | None
    missing_fields: tuple[str, ...] = ()
    status_label: str = ""


def clarification_email(reference: str, operations: list[OperationMailView]) -> tuple[str, str]:
    subject = f"[{reference}] Informations manquantes"
    lines = ["Bonjour,", "", "Nous avons identifié la demande suivante :", ""]
    for operation in operations:
        lines.append(
            f"Opération OP-{operation.sequence_number:02d} : {ACTION_LABELS.get(operation.action, operation.action)}"
        )
        if operation.pdv_code:
            lines.append(f"PDV : {operation.pdv_code}")
        labels = ", ".join(FIELD_LABELS.get(field, field) for field in operation.missing_fields)
        lines.append(f"Information manquante : {labels}")
        lines.append("")
    lines.extend(
        [
            "Merci de répondre directement à ce même email en précisant ces informations.",
            "",
            f"Référence : {reference}",
            "",
            "Cordialement,",
            "Support SNOC",
        ]
    )
    return subject, "\n".join(lines)


def completion_email(reference: str, operations: list[OperationMailView]) -> tuple[str, str]:
    subject = f"[{reference}] Résultat de traitement"
    lines = ["Bonjour,", "", f"Résultat de la demande {reference} :", ""]
    for operation in operations:
        pdv = f" du PDV {operation.pdv_code}" if operation.pdv_code else ""
        lines.append(
            f"OP-{operation.sequence_number:02d} — {ACTION_LABELS.get(operation.action, operation.action)}{pdv} : {operation.status_label}"
        )
    lines.extend(["", completion_marker(reference), "", "Cordialement,", "Support SNOC"])
    return subject, "\n".join(lines)
