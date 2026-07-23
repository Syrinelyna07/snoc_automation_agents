"""Data-quality score semantics shared by API tests and diagnostics."""

from __future__ import annotations

from collections.abc import Iterable


def weighted_dimension_score(rows: Iterable[tuple[int, int]]) -> float | None:
    """Return the official record-weighted score, never an equal-rule average."""

    passed = 0
    total = 0
    for passed_rows, total_rows in rows:
        if passed_rows < 0 or total_rows < 0 or passed_rows > total_rows:
            raise ValueError("DQ row counts must satisfy 0 <= passed_rows <= total_rows")
        passed += passed_rows
        total += total_rows
    return (100.0 * passed / total) if total else None
