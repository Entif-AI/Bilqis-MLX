"""Shared validation and canonical encoding for projection lifecycle records."""
from hashlib import sha256
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        _invalid("AKASHA_PROJECTION_VALUE_NOT_CANONICAL")


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))
