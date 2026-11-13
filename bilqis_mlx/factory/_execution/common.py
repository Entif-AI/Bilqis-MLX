"""Factory execution common owner."""
from __future__ import annotations

from .. import execution as _api


def _digest(value) -> str:
    return _api.hashlib.sha256(_api.json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def _pairs(value) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if value is None:
        return ()
    result = tuple((str(key), tuple(items)) for key, items in value)
    if (len({key for key, _ in result}) != len(result) or
            any(not key or not items or len(set(items)) != len(items) or
                any(not isinstance(item, str) or not item for item in items)
                for key, items in result)):
        raise ValueError("FACTORY_PROFILE_DIMENSION_INVALID")
    return result
