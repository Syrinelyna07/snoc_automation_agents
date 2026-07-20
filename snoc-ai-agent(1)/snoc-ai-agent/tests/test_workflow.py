"""
Tests du workflow multi-agents.
Lancer avec: pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.workflow.graph import process_email


def test_whitelisted_unlock_account_auto_executes():
    email = {
        "id": "t1",
        "sender": "animateur.zone1@company.com",
        "subject": "Déblocage compte",
        "body": "Bonjour, merci de débloquer le compte PDV-45210. Cordialement, Karim",
    }
    state = process_email(email)
    assert state["is_whitelisted"] is True
    assert state["intent"] == "unlock_account"
    assert state["decision"] == "auto_execute"
    assert state["execution_status"] == "success"
    assert state["execution_details"]["new_status"] == "active"


def test_non_whitelisted_sender_is_rejected():
    email = {
        "id": "t2",
        "sender": "random.person@gmail.com",
        "subject": "besoin d'aide",
        "body": "Débloquez mon compte PDV-45210 svp",
    }
    state = process_email(email)
    assert state["rejected"] is True
    assert "reply_text" in state


def test_missing_entity_triggers_clarification():
    email = {
        "id": "t3",
        "sender": "helpdesk@company.com",
        "subject": "help",
        "body": "bjr jss bloké c urgent",
    }
    state = process_email(email)
    assert state["decision"] == "clarify"
    assert state["execution_status"] == "skipped"


def test_nonexistent_pdv_fails_verification_and_escalates():
    email = {
        "id": "t4",
        "sender": "helpdesk@company.com",
        "subject": "Déblocage",
        "body": "Merci de débloquer le compte PDV-00000, c'est urgent.",
    }
    state = process_email(email)
    assert state["verification_passed"] is False
    assert state["decision"] == "escalate"
    assert state["execution_status"] == "skipped"


def test_create_pdv_account_extracts_structured_fields():
    email = {
        "id": "t5",
        "sender": "animateur.zone1@company.com",
        "subject": "Nouveau partenaire",
        "body": "Nom: Boutique Test\nCode PDV: PDV-12345\nTéléphone: 0770000000\nZone: Centre\n\nMerci de créer le compte.",
    }
    state = process_email(email)
    assert state["entities"]["partner_name"] == "Boutique Test"
    assert state["entities"]["zone"] == "Centre"
    assert state["decision"] == "auto_execute"
    assert state["execution_status"] == "success"


def test_english_reply_uses_english_template():
    email = {
        "id": "t6",
        "sender": "helpdesk@company.com",
        "subject": "Reactivation",
        "body": "Hello, could you please reactivate account PDV-33190? Thanks.",
    }
    state = process_email(email)
    assert state["detected_language"] == "en"
    assert "Hello" in state["reply_text"]


def test_arabic_email_extracts_entities():
    email = {
        "id": "t7",
        "sender": "animateur.zone2@company.com",
        "subject": "تحديث رقم الهاتف",
        "body": "من فضلكم قوموا بتحديث رقم الهاتف الخاص بـ OTP لنقطة البيع PDV-77102 الى الرقم 0661223344",
    }
    state = process_email(email)
    assert state["detected_language"] == "ar"
    assert state["entities"]["pdv_code"] == "PDV-77102"
    assert state["entities"]["phone_number"] == "0661223344"


def test_audit_record_is_persisted():
    email = {
        "id": "t8",
        "sender": "animateur.zone1@company.com",
        "subject": "Déblocage",
        "body": "Débloquer PDV-45210 svp",
    }
    state = process_email(email)
    assert state["audit_id"] == "t8"
