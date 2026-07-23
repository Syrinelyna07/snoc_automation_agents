from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from snoc_agent.db.base import utc_now
from snoc_agent.db.models import OutboxMessage
from snoc_agent.domain.enums import OutboxStatus


class OutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, message: OutboxMessage) -> OutboxMessage:
        self.session.add(message)
        self.session.flush()
        return message

    def claim_pending(
        self,
        limit: int = 100,
        *,
        lease_seconds: int = 300,
    ) -> list[OutboxMessage]:
        now = utc_now()
        stale = now - timedelta(seconds=lease_seconds)
        rows = list(
            self.session.scalars(
                select(OutboxMessage)
                .where(
                    or_(
                        (
                            (OutboxMessage.status == OutboxStatus.PENDING.value)
                            & (
                                (OutboxMessage.next_attempt_at.is_(None))
                                | (OutboxMessage.next_attempt_at <= now)
                            )
                        ),
                        (
                            (OutboxMessage.status == OutboxStatus.SENDING.value)
                            & (OutboxMessage.claimed_at < stale)
                        ),
                    )
                )
                .order_by(OutboxMessage.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for message in rows:
            message.status = OutboxStatus.SENDING.value
            message.claimed_at = now
        self.session.flush()
        return rows
