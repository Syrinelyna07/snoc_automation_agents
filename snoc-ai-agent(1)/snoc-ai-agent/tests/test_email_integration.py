import os

from app.integrations import email_mock
from app import config


class FakeIMAP:
    def __init__(self, *args, **kwargs):
        self.login_calls = []
        self.selected_mailbox = None

    def login(self, username, password):
        self.login_calls.append((username, password))
        return "OK", [b"Logged in"]

    def select(self, mailbox):
        self.selected_mailbox = mailbox
        return "OK", [b"INBOX"]

    def search(self, charset, criterion):
        return "OK", [b"1"]

    def fetch(self, message_id, message_parts):
        payload = (
            b"From: snocagent.test@gmail.com\r\n"
            b"To: support@example.com\r\n"
            b"Subject: Password reset request\r\n"
            b"\r\n"
            b"Hello, I need a password reset."
        )
        return "OK", [(b"1 (RFC822 {123}", payload), (b")", b"")]

    def logout(self):
        return "BYE", [b"Logged out"]


def test_fetch_inbox_uses_imap_when_configured(monkeypatch):
    monkeypatch.setenv("EMAIL_ADDRESS", "snocagent.test@gmail.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "app-password")
    monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.gmail.com")
    monkeypatch.setenv("EMAIL_IMAP_PORT", "993")

    monkeypatch.setattr(email_mock.imaplib, "IMAP4_SSL", lambda *args, **kwargs: FakeIMAP())

    messages = email_mock.fetch_inbox()

    assert len(messages) == 1
    assert messages[0]["sender"] == "snocagent.test@gmail.com"
    assert messages[0]["subject"] == "Password reset request"
    assert "need a password reset" in messages[0]["body"]


def test_config_loads_values_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("EMAIL_ADDRESS=demo@example.com\nEMAIL_PASSWORD=demo-pass\n", encoding="utf-8")

    monkeypatch.delenv("EMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    config._load_env_file(env_file)

    assert os.environ.get("EMAIL_ADDRESS") == "demo@example.com"
    assert os.environ.get("EMAIL_PASSWORD") == "demo-pass"
