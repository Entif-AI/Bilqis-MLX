"""Registry AST canonical text, reference, and digest helpers."""
from __future__ import annotations
import hashlib
import json
import re

GRADE_ID = re.compile(r"[A-Z]")

def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()

def _text(row: list, i: int) -> str:
    return str(row[i]).strip() if i < len(row) and row[i] is not None else ""

def _grade_refs(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    grades = tuple(s for s in re.split(r"[,;\s]+", value) if s)
    if not grades or any(not GRADE_ID.fullmatch(g) for g in grades):
        raise ValueError("REGISTRY_UNRESOLVED_GRADE_REFERENCE:" + value)
    if len(set(grades)) != len(grades):
        raise ValueError("REGISTRY_DUPLICATE_GRADE_REFERENCE")
    return grades
