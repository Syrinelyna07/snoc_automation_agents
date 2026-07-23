"""Standalone API process entrypoint."""

from __future__ import annotations

import uvicorn

from snoc_agent.api.app import create_app
from snoc_agent.config import load_settings


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.casefold(),
    )


if __name__ == "__main__":
    run()
