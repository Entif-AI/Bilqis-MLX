"""Registry AST canonical text, reference, and digest helpers."""
from __future__ import annotations
import hashlib
import json


def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()

def _text(row: list, i: int) -> str:
    return str(row[i]).strip() if i < len(row) and row[i] is not None else ""
