"""
Modèles de données partagés par tous les agents du workflow.
Le WorkflowState est l'objet d'état LangGraph qui transite entre chaque noeud du graphe.
"""
from __future__ import annotations
from typing import TypedDict, Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum


class DecisionType(str, Enum):
    AUTO_EXECUTE = "auto_execute"
    CLARIFY = "clarify"
    ESCALATE = "escalate"
    REJECT = "reject"


class IncomingEmail(BaseModel):
    id: str
    sender: str
    subject: str
    body: str
    attachments: List[str] = []


class ExtractedEntities(BaseModel):
    pdv_code: Optional[str] = None
    phone_number: Optional[str] = None
    partner_name: Optional[str] = None
    employee_id: Optional[str] = None
    zone: Optional[str] = None
    raw_entities: Dict[str, Any] = {}


class AuditRecord(BaseModel):
    request_id: str
    sender: str
    intent: str
    confidence: float
    decision: str
    execution_result: Optional[str] = None
    timestamp: str


class WorkflowState(TypedDict, total=False):
    # 1. Email Gateway
    id: str  # raw transport message id, consumed by the Ingress component
    request_id: str
    sender: str
    subject: str
    body: str
    attachments: List[str]

    # 2. Security & Whitelist
    is_whitelisted: bool
    sender_profile: Optional[Dict[str, Any]]
    rejected: bool
    rejection_reason: Optional[str]

    # 3. Understanding
    cleaned_text: str
    detected_language: str
    normalized_prompt: str

    # 4. Intent Classification
    intent: str
    intent_confidence: float

    # 5. Information Extraction
    entities: Dict[str, Any]

    # 6. Decision
    decision: str
    decision_reason: str

    # 7. Verification
    verification_passed: bool
    verification_issues: List[str]

    # 8. Execution
    execution_status: str
    execution_details: Dict[str, Any]

    # 9. Audit
    audit_id: str

    # 10. Reply
    reply_text: str

    # 11. Continuous learning
    learning_notes: List[str]

    # Trace complète (pour debug / démonstration)
    trace: List[str]
