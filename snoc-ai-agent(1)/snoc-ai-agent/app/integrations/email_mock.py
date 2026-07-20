"""Passerelle email IMAP/SMTP compatible Gmail.

Par défaut, si aucune configuration mail n'est fournie, la passerelle utilise les
emails de démonstration stockés dans app/data/sample_emails.json pour garder le
prototype fonctionnel sans dépendance externe.
"""
import email
import imaplib
import json
import os
import smtplib
import random
from email.header import decode_header
from email.message import EmailMessage

from app import config
from app.config import SAMPLE_EMAILS_PATH

_OUTBOX: list[dict] = []


def _get_mail_settings() -> dict:
    return {
        "address": os.environ.get("EMAIL_ADDRESS", config.EMAIL_ADDRESS),
        "password": os.environ.get("EMAIL_PASSWORD", config.EMAIL_PASSWORD),
        "imap_host": os.environ.get("EMAIL_IMAP_HOST", config.EMAIL_IMAP_HOST),
        "imap_port": int(os.environ.get("EMAIL_IMAP_PORT", config.EMAIL_IMAP_PORT)),
        "imap_mailbox": os.environ.get("EMAIL_IMAP_MAILBOX", config.EMAIL_IMAP_MAILBOX),
        "smtp_host": os.environ.get("EMAIL_SMTP_HOST", config.EMAIL_SMTP_HOST),
        "smtp_port": int(os.environ.get("EMAIL_SMTP_PORT", config.EMAIL_SMTP_PORT)),
    }


def _load_mock_emails() -> list[dict]:
    with open(SAMPLE_EMAILS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    decoded_parts = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="ignore"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def _extract_body(message: email.message.Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "text" and part.get_content_subtype() in {"plain", "html"}:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
    payload = message.get_payload(decode=True)
    if payload:
        return payload.decode(message.get_content_charset() or "utf-8", errors="ignore")
    return ""


def _parse_message(raw_message: bytes) -> dict:
    message = email.message_from_bytes(raw_message)
    sender = _decode_header(message.get("From", ""))
    subject = _decode_header(message.get("Subject", ""))
    body = _extract_body(message)
    attachments = []
    for part in message.walk():
        if part.get_content_disposition() == "attachment":
            attachments.append(part.get_filename() or "attachment")
    return {
        "id": message.get("Message-ID", ""),
        "sender": sender,
        "subject": subject,
        "body": body.strip(),
        "attachments": attachments,
    }


_MOCK_SUPERVISORS = [
    {"email": "amina.east@djezzy.dz",      "zone": "Zone East"},
    {"email": "karim.benaissa@djezzy.dz",  "zone": "Zone East"},
    {"email": "yasmine.hamdi@djezzy.dz",   "zone": "Zone East"},
    {"email": "ahmed.saidi@djezzy.dz",     "zone": "Zone East"},
    {"email": "malik.center@djezzy.dz",    "zone": "Zone Center"},
    {"email": "nadia.bouzid@djezzy.dz",    "zone": "Zone Center"},
    {"email": "farid.center@djezzy.dz",    "zone": "Zone Center"},
    {"email": "lamia.hadjar@djezzy.dz",    "zone": "Zone Center"},
    {"email": "sofiane.west@djezzy.dz",    "zone": "Zone West"},
    {"email": "wassim.belkacem@djezzy.dz", "zone": "Zone West"},
    {"email": "imane.cherif@djezzy.dz",    "zone": "Zone West"},
    {"email": "rachid.benmoussa@djezzy.dz","zone": "Zone West"},
    {"email": "bilal.south@djezzy.dz",     "zone": "South Region"},
    {"email": "meriem.dahmani@djezzy.dz",  "zone": "South Region"},
    {"email": "tarek.messaoudi@djezzy.dz", "zone": "South Region"}
]

_MOCK_SUSPICIOUS = [
    {"email": "gmail.contact92@gmail.com", "zone": "Zone East"},
    {"email": "no-reply@promo-deals.biz",  "zone": "Zone West"},
    {"email": "unknown.user@webmail.dz",   "zone": "Zone Center"}
]

_MOCK_TEMPLATES = [
    {
        "intent": "unlock_account",
        "subject": "Déblocage compte PDV urgent",
        "body": "Bonjour,\n\nLe compte associé au PDV {pdv} est bloqué depuis ce matin. Merci de le débloquer rapidement, le point de vente ne peut plus encaisser.\n\nCordialement.",
        "need_pdv": True
    },
    {
        "intent": "reset_password",
        "subject": "Reset password stp",
        "body": "Bonjour,\n\nJe n'arrive plus à me connecter au PDV {pdv}. Pouvez-vous réinitialiser le mot de passe ?\n\nMerci.",
        "need_pdv": True
    },
    {
        "intent": "reactivate_account",
        "subject": "Reactivation account inactive",
        "body": "Bonjour,\n\nLe compte du PDV {pdv} a été suspendu par erreur, merci de le réactiver dès que possible.\n\nCordialement.",
        "need_pdv": True
    },
    {
        "intent": "update_otp_phone",
        "subject": "Mise à jour OTP",
        "body": "Bonjour,\n\nMerci de mettre à jour le numéro OTP du PDV {pdv} vers le {phone}.\n\nCordialement.",
        "need_pdv": True,
        "need_phone": True
    },
    {
        "intent": "create_pdv_account",
        "subject": "Nouveau partenaire - création compte",
        "body": "Bonjour,\n\nNous avons un nouveau partenaire à intégrer:\nNom: Boutique {partner}\nCode PDV: {pdv}\nTéléphone: {phone}\nZone: {zone}\n\nMerci de créer le compte.\n\nCordialement.",
        "need_pdv": True,
        "need_phone": True,
        "need_partner": True
    },
    {
        "intent": "create_vpn_account",
        "subject": "VPN Access Creation",
        "body": "Hi, need VPN account creation for new field agent, name {agent_name}, employee id {emp_id}. Thx.",
        "need_emp": True
    },
    {
        "intent": "unknown",
        "subject": "Rappel: réunion d'équipe",
        "body": "Bonjour, je vous rappelle que la réunion hebdomadaire est programmée pour ce jeudi à 14h. Merci.",
        "need_irrelevant": True
    }
]

_MOCK_PARTNERS = ["El Amir", "Nour", "Anis", "Bilal", "Rania", "Standard", "West Express", "Djezzy Shop"]
_MOCK_FIRST_NAMES = ["Karim", "Amina", "Omar", "Yasmine", "Ahmed", "Malik", "Nadia", "Farid", "Sofiane", "Imane"]
_MOCK_LAST_NAMES = ["Belkacem", "Benaissa", "Hamdi", "Saidi", "Bouzid", "Hadjar", "Cherif", "Benmoussa", "Dahmani", "Saadi"]

def generate_random_email() -> dict:
    sender_obj = random.choice(_MOCK_SUSPICIOUS) if random.random() < 0.05 else random.choice(_MOCK_SUPERVISORS)
    template = random.choice(_MOCK_TEMPLATES)
    
    pdv = f"PDV-{random.randint(10000, 99999)}"
    phone = f"0{random.choice([5, 6, 7])}{random.randint(10, 99)}{random.randint(10, 99)}{random.randint(10, 99)}{random.randint(10, 99)}"
    partner = random.choice(_MOCK_PARTNERS)
    agent_name = f"{random.choice(_MOCK_FIRST_NAMES)} {random.choice(_MOCK_LAST_NAMES)}"
    emp_id = f"EMP-{random.randint(1000, 9999)}"
    
    body = template["body"].format(
        pdv=pdv,
        phone=phone,
        partner=partner,
        agent_name=agent_name,
        emp_id=emp_id,
        zone=sender_obj["zone"]
    )
    
    email_id = f"email_mock_{random.randint(10000000, 99999999)}"
    return {
        "id": email_id,
        "sender": sender_obj["email"],
        "subject": template["subject"],
        "body": body,
        "attachments": []
    }


def fetch_inbox() -> list[dict]:
    """Lit la boîte IMAP si des identifiants sont fournis, sinon retombe sur les emails mockés."""
    settings = _get_mail_settings()
    if not settings["address"] or not settings["password"]:
        emails = _load_mock_emails()
        # 30% chance to append a newly generated mock email to simulate ongoing traffic
        if random.random() < 0.30:
            emails.append(generate_random_email())
        return emails

    try:
        server = imaplib.IMAP4_SSL(settings["imap_host"], settings["imap_port"])
        server.login(settings["address"], settings["password"])
        server.select(settings["imap_mailbox"])
        status, data = server.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError("IMAP search failed")

        message_ids = []
        if data and data[0]:
            message_ids = [item.decode("utf-8", errors="ignore").strip() for item in data[0].split()]

        messages = []
        for message_id in message_ids:
            status, message_data = server.fetch(message_id, "(RFC822)")
            if status != "OK":
                continue
            for item in message_data:
                if isinstance(item, tuple) and isinstance(item[1], bytes):
                    messages.append(_parse_message(item[1]))
                    break

        server.logout()
        return messages
    except Exception:
        return []


def send_reply(to: str, subject: str, body: str) -> dict:
    """Envoie la réponse par SMTP si les credentials sont disponibles, sinon l'enregistre localement."""
    settings = _get_mail_settings()
    message = {"to": to, "subject": subject, "body": body, "delivery_status": "mocked"}
    if not settings["address"] or not settings["password"]:
        _OUTBOX.append(message)
        return message

    try:
        msg = EmailMessage()
        msg["From"] = settings["address"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        if settings["smtp_port"] == 465:
            server = smtplib.SMTP_SSL(settings["smtp_host"], settings["smtp_port"])
        else:
            server = smtplib.SMTP(settings["smtp_host"], settings["smtp_port"])
            server.starttls()

        server.login(settings["address"], settings["password"])
        server.send_message(msg)
        server.quit()
    except Exception:
        message["delivery_status"] = "failed"
        _OUTBOX.append(message)
        return message

    message["delivery_status"] = "sent"
    _OUTBOX.append(message)
    return message


def get_outbox() -> list[dict]:
    return list(_OUTBOX)
