"""MIME body and attachment extraction helpers."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from email.message import Message
from html.parser import HTMLParser
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class ContentLimits:
    max_text_part_bytes: int
    max_html_part_bytes: int
    max_attachment_count: int
    max_attachment_bytes: int


class _TextExtractor(HTMLParser):
    BLOCK_TAGS: ClassVar[set[str]] = {
        "p",
        "div",
        "br",
        "li",
        "tr",
        "h1",
        "h2",
        "h3",
        "blockquote",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.ignored_depth += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(value)
        text = "".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in html.unescape(text).splitlines()]
    return "\n".join(line for line in lines if line)


def decode_part(part: Message, *, max_bytes: int | None = None) -> tuple[str, bool]:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        text = raw if isinstance(raw, str) else ""
        if max_bytes is not None and len(text.encode("utf-8")) > max_bytes:
            return text.encode("utf-8")[:max_bytes].decode("utf-8", errors="replace"), True
        return text, False
    if not isinstance(payload, bytes):
        return str(payload), False
    truncated = max_bytes is not None and len(payload) > max_bytes
    if truncated:
        payload = payload[:max_bytes]
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace"), truncated
    except LookupError:
        return payload.decode("utf-8", errors="replace"), truncated


def extract_content(
    message: Message, *, limits: ContentLimits | None = None
) -> tuple[str, str | None, list[dict[str, Any]], list[str]]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict[str, Any]] = []
    warnings: list[str] = []

    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition == "attachment" or filename:
            if limits is not None and len(attachments) >= limits.max_attachment_count:
                if "attachment_count_limit_exceeded" not in warnings:
                    warnings.append("attachment_count_limit_exceeded")
                continue
            decoded_payload = part.get_payload(decode=True)
            payload = decoded_payload if isinstance(decoded_payload, bytes) else b""
            oversized = limits is not None and len(payload) > limits.max_attachment_bytes
            metadata = {
                "filename": filename or "unnamed",
                "content_type": content_type,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            if oversized:
                metadata["exceeds_size_limit"] = True
            attachments.append(metadata)
            if oversized and "attachment_size_limit_exceeded" not in warnings:
                warnings.append("attachment_size_limit_exceeded")
            continue
        if content_type == "text/plain":
            decoded, truncated = decode_part(
                part,
                max_bytes=limits.max_text_part_bytes if limits is not None else None,
            )
            plain_parts.append(decoded)
            if truncated and "text_part_limit_exceeded" not in warnings:
                warnings.append("text_part_limit_exceeded")
        elif content_type == "text/html":
            decoded, truncated = decode_part(
                part,
                max_bytes=limits.max_html_part_bytes if limits is not None else None,
            )
            html_parts.append(decoded)
            if truncated and "html_part_limit_exceeded" not in warnings:
                warnings.append("html_part_limit_exceeded")

    html_body = "\n".join(html_parts).strip() or None
    if plain_parts:
        plain = "\n".join(plain_parts).strip()
    elif html_body:
        plain = html_to_text(html_body)
        warnings.append("html_only_body_converted_to_text")
    else:
        plain = ""
        warnings.append("no_supported_text_body")
    return plain, html_body, attachments, warnings
