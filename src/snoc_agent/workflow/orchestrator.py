"""Polling orchestrator that processes each fetched message independently."""

from __future__ import annotations

import logging
import uuid

from snoc_agent.mail.interfaces import IMAPMailbox
from snoc_agent.workflow.inbound_processor import (
    InboundIdentity,
    InboundProcessor,
    ProcessingResult,
)

LOGGER = logging.getLogger(__name__)


class MailOrchestrator:
    def __init__(
        self,
        *,
        mailbox: IMAPMailbox,
        processor: InboundProcessor,
        mail_account_id: uuid.UUID,
    ) -> None:
        self.mailbox = mailbox
        self.processor = processor
        self.mail_account_id = mail_account_id

    def poll_once(self) -> list[ProcessingResult]:
        results: list[ProcessingResult] = []
        for message in self.mailbox.fetch_candidates():
            try:
                results.append(
                    self.processor.process_raw(
                        message.raw_message,
                        identity=InboundIdentity(
                            account_id=self.mail_account_id,
                            mailbox=message.mailbox,
                            uidvalidity=message.uidvalidity,
                            uid=message.uid,
                            internal_date=message.internal_date,
                            flags=message.flags,
                            provider_metadata=message.provider_metadata,
                        ),
                    )
                )
            except Exception:
                LOGGER.exception("one IMAP message failed; continuing with the remaining UIDs")
        return results
