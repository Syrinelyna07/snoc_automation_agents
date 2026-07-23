"""Synchronous UID-based IMAP implementation using BODY.PEEK."""

from __future__ import annotations

import imaplib
import logging
import re
from contextlib import suppress
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from snoc_agent.mail.interfaces import MailboxMessage

UIDVALIDITY_RE = re.compile(rb"UIDVALIDITY\s+(\d+)", re.IGNORECASE)
FLAGS_RE = re.compile(rb"FLAGS\s*\(([^)]*)\)", re.IGNORECASE)
INTERNALDATE_RE = re.compile(rb'INTERNALDATE\s+"([^"]+)"', re.IGNORECASE)
LOGGER = logging.getLogger(__name__)


class RealIMAPMailbox:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        mailbox: str = "INBOX",
        use_ssl: bool = True,
        search_criterion: str = "ALL",
        timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.use_ssl = use_ssl
        self.search_criterion = search_criterion
        self.timeout = timeout

    def _connect(self) -> imaplib.IMAP4:
        cls = imaplib.IMAP4_SSL if self.use_ssl else imaplib.IMAP4
        connection = cls(self.host, self.port, timeout=self.timeout)
        connection.login(self.username, self.password)
        return connection

    @staticmethod
    def _uidvalidity(connection: imaplib.IMAP4) -> int:
        status, values = connection.response("UIDVALIDITY")
        joined = b" ".join(value for value in (values or []) if isinstance(value, bytes))
        match = UIDVALIDITY_RE.search(joined)
        if status != "UIDVALIDITY":
            raise RuntimeError(f"IMAP server did not provide UIDVALIDITY: {status!r} {values!r}")
        # imaplib commonly returns ``[b"123"]`` for response("UIDVALIDITY"),
        # while some servers include the response-code label in the value.
        if joined.strip().isdigit():
            return int(joined.strip())
        if not match:
            raise RuntimeError(f"IMAP server did not provide UIDVALIDITY: {status!r} {values!r}")
        return int(match.group(1))

    @staticmethod
    def _parse_fetch(
        uid: int, response: list[bytes | tuple[bytes, bytes] | None]
    ) -> tuple[bytes, datetime | None, tuple[str, ...]]:
        raw: bytes | None = None
        metadata = b""
        for item in response:
            if isinstance(item, tuple):
                metadata += item[0]
                raw = item[1]
            elif isinstance(item, bytes):
                metadata += item
        if raw is None:
            raise RuntimeError(f"UID FETCH {uid} returned no RFC822 payload: {response!r}")
        flags_match = FLAGS_RE.search(metadata)
        flags = (
            tuple(flags_match.group(1).decode("ascii", "replace").split()) if flags_match else ()
        )
        date_match = INTERNALDATE_RE.search(metadata)
        internal_date: datetime | None = None
        if date_match:
            try:
                internal_date = parsedate_to_datetime(
                    date_match.group(1).decode("ascii")
                ).astimezone(UTC)
            except (TypeError, ValueError, OverflowError):
                internal_date = None
        return raw, internal_date, flags

    def fetch_candidates(self) -> list[MailboxMessage]:
        connection = self._connect()
        try:
            status, select_data = connection.select(self.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"cannot select mailbox {self.mailbox!r}: {select_data!r}")
            uidvalidity = self._uidvalidity(connection)
            # imaplib requires ``None`` here to omit the optional SEARCH charset;
            # typeshed models UID arguments as strings only.
            search_charset: Any = None
            status, search_data = connection.uid(
                "SEARCH",
                search_charset,
                self.search_criterion,
            )
            if status != "OK":
                raise RuntimeError(f"UID SEARCH failed: {search_data!r}")
            uid_blob = b" ".join(value for value in search_data if isinstance(value, bytes))
            messages: list[MailboxMessage] = []
            for token in uid_blob.split():
                uid = int(token)
                try:
                    fetch_status, fetch_data = connection.uid(
                        "FETCH", str(uid), "(BODY.PEEK[] INTERNALDATE FLAGS UID)"
                    )
                    if fetch_status != "OK":
                        raise RuntimeError(f"UID FETCH {uid} failed: {fetch_data!r}")
                    raw, internal_date, flags = self._parse_fetch(uid, fetch_data)
                except (RuntimeError, TypeError, ValueError):
                    # This UID remains discoverable in the next poll; later UIDs still progress.
                    LOGGER.exception("one UID FETCH failed; continuing", extra={"imap_uid": uid})
                    continue
                messages.append(
                    MailboxMessage(
                        mailbox=self.mailbox,
                        uidvalidity=uidvalidity,
                        uid=uid,
                        raw_message=raw,
                        internal_date=internal_date,
                        flags=flags,
                    )
                )
            return messages
        finally:
            with suppress(imaplib.IMAP4.error):
                connection.logout()
