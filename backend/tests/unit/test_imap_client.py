from __future__ import annotations

from datetime import UTC, datetime

from snoc_agent.mail.imap_client import RealIMAPMailbox


class _IMAPConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.logged_out = False

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        self.calls.append(("LOGIN", username, password))
        return "OK", []

    def select(self, mailbox: str, readonly: bool) -> tuple[str, list[bytes]]:
        self.calls.append(("SELECT", mailbox, readonly))
        return "OK", [b"2"]

    def response(self, code: str) -> tuple[str, list[bytes]]:
        self.calls.append(("RESPONSE", code))
        # This is the common imaplib shape: the response code is the status and
        # the value itself is numeric, without an embedded UIDVALIDITY label.
        return "UIDVALIDITY", [b"777"]

    def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
        self.calls.append(("UID", command, *args))
        if command == "SEARCH":
            return "OK", [b"9 10 11"]
        uid = str(args[0])
        if uid == "10":
            return "NO", [b"temporary fetch failure"]
        if uid == "9":
            metadata = (
                b'9 (UID 9 INTERNALDATE "18-Jul-2026 10:11:12 +0000" '
                b"FLAGS (\\Seen \\Flagged) BODY[] {14}"
            )
            return "OK", [(metadata, b"Subject: one\r\n\r\nA"), b")"]
        return "OK", [(b"11 (UID 11 FLAGS () BODY[] {14}", b"Subject: two\r\n\r\nB"), b")"]

    def logout(self) -> tuple[str, list[bytes]]:
        self.logged_out = True
        return "BYE", []


def test_real_imap_fetches_metadata_with_body_peek_and_skips_one_bad_uid(monkeypatch) -> None:
    connection = _IMAPConnection()
    monkeypatch.setattr(
        "snoc_agent.mail.imap_client.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: connection,
    )
    mailbox = RealIMAPMailbox(
        host="imap.example.invalid",
        port=993,
        username="agent@example.invalid",
        password="not-a-real-password",
        mailbox="Requests",
    )

    messages = mailbox.fetch_candidates()

    assert [(message.uidvalidity, message.uid) for message in messages] == [(777, 9), (777, 11)]
    assert messages[0].flags == ("\\Seen", "\\Flagged")
    assert messages[0].internal_date == datetime(2026, 7, 18, 10, 11, 12, tzinfo=UTC)
    assert messages[1].flags == ()
    assert messages[1].internal_date is None
    assert ("SELECT", "Requests", True) in connection.calls
    assert ("UID", "SEARCH", None, "ALL") in connection.calls
    assert all(
        "BODY.PEEK[]" in str(call) for call in connection.calls if call[:2] == ("UID", "FETCH")
    )
    assert connection.logged_out is True
