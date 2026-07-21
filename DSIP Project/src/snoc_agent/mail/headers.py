"""RFC header decoding and conservative normalization."""

from __future__ import annotations

import re
from email.header import decode_header, make_header
from email.utils import getaddresses

MESSAGE_ID_RE = re.compile(r"<\s*([^<>\s]+)\s*>")
SUBJECT_PREFIX_RE = re.compile(r"^\s*(?:re|tr|fw|fwd)\s*[:\uFF1A-]+\s*", re.IGNORECASE)


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (LookupError, UnicodeError):
        return value.strip()


def normalize_message_id(value: str | None) -> str | None:
    """Normalize an RFC Message-ID for comparison while retaining angle brackets."""

    if not value:
        return None
    match = MESSAGE_ID_RE.search(value)
    candidate = match.group(1) if match else value.strip().strip("<>").strip()
    if not candidate or any(character.isspace() for character in candidate):
        return None
    return f"<{candidate.casefold()}>"


def parse_references(value: str | None) -> list[str]:
    if not value:
        return []
    matches = [normalize_message_id(match) for match in MESSAGE_ID_RE.findall(value)]
    normalized = [match for match in matches if match is not None]
    if not normalized:
        normalized = [
            item for token in value.split() if (item := normalize_message_id(token)) is not None
        ]
    return list(dict.fromkeys(normalized))


def normalize_subject(value: str | None) -> str:
    subject = decode_header_value(value)
    previous = None
    while subject != previous:
        previous = subject
        subject = SUBJECT_PREFIX_RE.sub("", subject, count=1).strip()
    return re.sub(r"\s+", " ", subject).casefold()


def decoded_addresses(values: list[str]) -> list[str]:
    decoded: list[str] = []
    for display_name, address in getaddresses(values):
        if not address:
            continue
        name = decode_header_value(display_name)
        decoded.append(f"{name} <{address}>" if name else address)
    return decoded


def bare_address(value: str) -> str:
    addresses = getaddresses([value])
    return addresses[0][1].strip().casefold() if addresses else ""


def build_references(previous: list[str], incoming_message_id: str | None) -> list[str]:
    values = [*previous]
    normalized = normalize_message_id(incoming_message_id)
    if normalized:
        values.append(normalized)
    return list(dict.fromkeys(values))
