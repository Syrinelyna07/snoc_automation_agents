"""Read-only HTTP API for health, operations, audit, and data-quality dashboards."""

from snoc_agent.api.app import create_app

__all__ = ["create_app"]
