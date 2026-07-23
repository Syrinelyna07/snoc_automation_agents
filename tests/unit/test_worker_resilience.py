from __future__ import annotations

from types import SimpleNamespace

import pytest

from snoc_agent.cli import commands


class _StopLoop(Exception):
    pass


class _TransientMailboxFailure:
    def poll_once(self) -> list[object]:
        raise OSError("temporary DNS failure")


class _RecordingOutbox:
    def __init__(self) -> None:
        self.calls = 0

    def send_once(self) -> tuple[int, int]:
        self.calls += 1
        return (0, 0)


def test_worker_survives_transient_imap_failure_and_still_drains_outbox(monkeypatch) -> None:
    outbox = _RecordingOutbox()
    runtime = SimpleNamespace(outbox=outbox)
    settings = SimpleNamespace(imap_poll_seconds=1)
    monkeypatch.setattr(
        commands,
        "_real_orchestrator",
        lambda _settings: (runtime, _TransientMailboxFailure()),
    )

    def stop_after_one_iteration(_seconds: float) -> None:
        raise _StopLoop

    monkeypatch.setattr(commands.time, "sleep", stop_after_one_iteration)

    with pytest.raises(_StopLoop):
        commands.worker_run(settings)  # type: ignore[arg-type]

    assert outbox.calls == 1
