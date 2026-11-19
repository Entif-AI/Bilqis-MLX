"""Shared canonical encoding and validation for Akasha security contracts."""
from hashlib import sha256
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


def invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)


def canonical(value: object) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        invalid("AKASHA_SECURITY_VALUE_NOT_CANONICAL")


def digest(value: object) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def is_digest(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def is_name(value: object) -> bool:
    return isinstance(value, str) and bool(_NAME.fullmatch(value))
