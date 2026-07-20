"""
Script de démonstration : traite l'ensemble des emails d'exemple (app/data/sample_emails.json)
à travers le workflow multi-agents complet, et affiche un rapport lisible.

Usage:
    python scripts/run_demo.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import init_db, fetch_kpis
from app.integrations.email_mock import fetch_inbox
from app.workflow.graph import process_email


def main():
    init_db()
    emails = fetch_inbox()

    print("=" * 90)
    print(f"DÉMONSTRATION — Agent IA SNOC — traitement de {len(emails)} emails")
    print("=" * 90)

    for email in emails:
        state = process_email(email)
        print(f"\n--- {email['id']} | de: {email['sender']} | sujet: {email['subject']}")
        for line in state["trace"]:
            print(f"    {line}")
        print(f"    >>> Réponse envoyée:\n{_indent(state['reply_text'])}")

    print("\n" + "=" * 90)
    print("KPI globaux après traitement du lot:")
    for k, v in fetch_kpis().items():
        print(f"  - {k}: {v}")
    print("=" * 90)


def _indent(text: str, prefix: str = "        ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


if __name__ == "__main__":
    main()
