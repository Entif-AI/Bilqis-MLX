"""Public-disclosure helpers for #39 source projection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from urllib.parse import unquote, urlsplit


PUBLIC_SOURCE_HOSTS = frozenset({"ithkuil.net", "www.ithkuil.net"})
LOCUS_BASE = "https://github.com/Entif-AI/Bilqis-MLX/source/locus/"
PRIVATE_LITERAL_MARKERS = (
    "file://",
    "localhost",
    "127.0.0.1",
    "github.com/",
    "/users/",
    "/home/",
    "\\",
)
MAX_CLASSIFICATION_DECODE_PASSES = 4


def decoded_classification_view(value: str) -> str | None:
    """Decode nested percent escapes for classification without rewriting source text.

    Return ``None`` when the input is still changing after the bounded decode budget
    or contains malformed UTF-8 escapes. Callers must treat that as unsafe.
    """
    classified = value
    for _ in range(MAX_CLASSIFICATION_DECODE_PASSES):
        try:
            decoded = unquote(classified, errors="strict")
        except UnicodeDecodeError:
            return None
        if decoded == classified:
            return classified
        classified = decoded
    try:
        if unquote(classified, errors="strict") != classified:
            return None
    except UnicodeDecodeError:
        return None
    return classified


@dataclass(frozen=True, order=True)
class PublicLocus:
    source_url: str
    source_id: str
    source_title: str
    coordinates: tuple[tuple[str, str], ...]
    identifier: str
    citation: str

    @property
    def iri(self) -> str:
        payload = json.dumps(
            {"source_url": self.source_url, "coordinates": self.coordinates},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return LOCUS_BASE + digest


def safe_public_literal(value: str) -> str | None:
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value):
        return None
    lowered = value.lower()
    classified = decoded_classification_view(lowered)
    if classified is None:
        return None
    if any(marker in classified for marker in PRIVATE_LITERAL_MARKERS):
        return None
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in classified):
        return None
    for embedded_url in re.findall(r"https?://[^\s;]+", classified):
        if not public_source_url(embedded_url):
            return None
    return value


def public_source_url(value: str) -> bool:
    # urlsplit discards some raw control characters. Reject them before parsing
    # rather than accidentally classifying a repaired URL as the source value.
    if not isinstance(value, str) or not value or any(
        character.isspace() or unicodedata.category(character) in {"Cc", "Cf", "Cs"}
        for character in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    if parsed.scheme != "https" or parsed.hostname not in PUBLIC_SOURCE_HOSTS:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if port not in (None, 443) or parsed.query or parsed.fragment:
        return False
    decoded = unquote(parsed.path)
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in decoded):
        return False
    if "\\" in decoded or any(part in {".", ".."} for part in decoded.split("/")):
        return False
    return True


def clean_locator_parts(
    parts: list[tuple[str, str]],
) -> tuple[tuple[str, str], ...] | None:
    output = []
    for label, value in parts:
        if not value:
            continue
        safe = safe_public_literal(value)
        if safe is None:
            return None
        output.append((label, safe))
    return tuple(output)
