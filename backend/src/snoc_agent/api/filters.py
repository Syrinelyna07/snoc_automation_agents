"""Validated UTC dashboard range parsing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from fastapi import HTTPException


class DateRange(StrEnum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class TimeWindow:
    range: DateRange
    start: datetime
    end: datetime


def parse_time_window(
    range_value: DateRange,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    now: datetime | None = None,
) -> TimeWindow:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)
    if range_value == DateRange.CUSTOM:
        if start is None or end is None:
            raise HTTPException(422, "custom range requires start and end")
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        if start >= end:
            raise HTTPException(422, "custom range start must be before end")
        if end - start > timedelta(days=366):
            raise HTTPException(422, "custom range cannot exceed 366 days")
        return TimeWindow(range_value, start, end)
    starts = {
        DateRange.TODAY: current.replace(hour=0, minute=0, second=0, microsecond=0),
        DateRange.WEEK: current - timedelta(days=7),
        DateRange.MONTH: current - timedelta(days=30),
        DateRange.YEAR: current - timedelta(days=365),
    }
    return TimeWindow(range_value, starts[range_value], current)


def range_query_values(
    range_value: DateRange,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, str]:
    values = {"range": range_value.value}
    if range_value == DateRange.CUSTOM and start is not None and end is not None:
        values.update({"start": start.isoformat(), "end": end.isoformat()})
    return values
