"""
Client mocké des API SNOC.
En production, ce module serait remplacé par de vrais appels REST/SOAP vers le système SNOC
(cf. Technologie: "connecteurs API vers systèmes IT").

Ici, on simule une base de comptes PDV en mémoire pour permettre une démonstration
end-to-end réaliste (comptes bloqués, inactifs, etc.).
"""
import random
import string
from datetime import datetime, timezone

# Base PDV simulée : code -> état du compte
_MOCK_PDV_DB = {
    "PDV-45210": {"status": "locked", "phone": "0555000001", "partner": "Superette Nour"},
    "PDV-88012": {"status": "active", "phone": "0555000002", "partner": "Epicerie Anis"},
    "PDV-33190": {"status": "inactive", "phone": "0555000003", "partner": "Market Bilal"},
    "PDV-77102": {"status": "active", "phone": "0555000004", "partner": "Superette Rania"},
}

_MOCK_VPN_DB = {}


class SNOCApiError(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def unlock_account(pdv_code: str) -> dict:
    account = _MOCK_PDV_DB.get(pdv_code)
    if not account:
        raise SNOCApiError(f"Compte PDV {pdv_code} introuvable dans SNOC.")
    account["status"] = "active"
    return {"pdv_code": pdv_code, "new_status": "active", "action": "unlock_account", "timestamp": _now()}


def reset_password(pdv_code: str) -> dict:
    account = _MOCK_PDV_DB.get(pdv_code)
    if not account:
        raise SNOCApiError(f"Compte PDV {pdv_code} introuvable dans SNOC.")
    new_password = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    return {
        "pdv_code": pdv_code,
        "action": "reset_password",
        "temporary_password": new_password,
        "timestamp": _now(),
    }


def reactivate_account(pdv_code: str) -> dict:
    account = _MOCK_PDV_DB.get(pdv_code)
    if not account:
        raise SNOCApiError(f"Compte PDV {pdv_code} introuvable dans SNOC.")
    if account["status"] != "inactive":
        return {
            "pdv_code": pdv_code,
            "action": "reactivate_account",
            "note": f"Le compte n'était pas inactif (statut actuel: {account['status']}).",
            "new_status": account["status"],
            "timestamp": _now(),
        }
    account["status"] = "active"
    return {"pdv_code": pdv_code, "new_status": "active", "action": "reactivate_account", "timestamp": _now()}


def update_otp_phone(pdv_code: str, new_phone: str) -> dict:
    account = _MOCK_PDV_DB.get(pdv_code)
    if not account:
        raise SNOCApiError(f"Compte PDV {pdv_code} introuvable dans SNOC.")
    old_phone = account["phone"]
    account["phone"] = new_phone
    return {
        "pdv_code": pdv_code,
        "action": "update_otp_phone",
        "old_phone": old_phone,
        "new_phone": new_phone,
        "timestamp": _now(),
    }


def create_pdv_account(partner_name: str, phone_number: str, zone: str = "N/A") -> dict:
    new_code = f"PDV-{random.randint(10000, 99999)}"
    _MOCK_PDV_DB[new_code] = {"status": "active", "phone": phone_number, "partner": partner_name}
    return {
        "pdv_code": new_code,
        "action": "create_pdv_account",
        "partner": partner_name,
        "phone": phone_number,
        "zone": zone,
        "timestamp": _now(),
    }


def create_vpn_account(employee_name: str, employee_id: str) -> dict:
    username = f"vpn_{employee_id.lower()}"
    _MOCK_VPN_DB[username] = {"name": employee_name, "employee_id": employee_id}
    return {
        "action": "create_vpn_account",
        "username": username,
        "employee_name": employee_name,
        "employee_id": employee_id,
        "timestamp": _now(),
    }


def get_account(pdv_code: str) -> dict | None:
    return _MOCK_PDV_DB.get(pdv_code)


# Registre des actions exécutables, utilisé par l'Execution Agent
ACTIONS = {
    "unlock_account": unlock_account,
    "reset_password": reset_password,
    "reactivate_account": reactivate_account,
    "update_otp_phone": update_otp_phone,
    "create_pdv_account": create_pdv_account,
    "create_vpn_account": create_vpn_account,
}
