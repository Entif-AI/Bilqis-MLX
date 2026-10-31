from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import string

def _display(value: Any, *, decimals: int = 3) -> str:
    if type(value) in (float, int):
        if value and abs(value) < 0.5 * 10 ** (-decimals):
            return f"{value:.2e}"
        return f"{value:.{decimals}f}"
    return "-"



def _inventory_scope(scope: str, caps: dict) -> str:
    """Internal comparison identity for the capability inventory actually scored."""
    return scope + "|inventory:" + ",".join(sorted(caps))



def _scaled_lr(value: Any) -> str:
    if type(value) not in (float, int):
        return "-"
    return str(int(value * 100000 + 0.5))



def _whole(value: Any) -> str:
    if type(value) not in (float, int):
        return "-"
    return str(int(value + 0.5))



def _score_quad(before: Any, top: Any, after: Any, total: Any) -> str:
    if not all(type(value) is int for value in (before, after, total)) or total <= 0:
        return "-"
    top_text = f"{top:>3}" if type(top) is int else "  -"
    return f"{before:>3}/{top_text}/{after:>3}/{total:>3}"



def _delta(value: Any, *, pp: bool = False) -> str:
    if type(value) not in (float, int):
        return "-"
    if pp:
        return f"{value:+.1f}pp"
    return f"{value:+.3f}"



def _percent(value: Any) -> str:
    return f"{value:.1%}" if type(value) in (float, int) else "-"



def _count(value: Any) -> str:
    return f"{value:,}" if type(value) is int else "-"



def _source_provenance(event: dict):
    """Independent metrics must identify their validation set and whole student."""
    for key in ("dataset_sha256", "student_sha256"):
        value = event.get(key)
        if (not isinstance(value, str) or len(value) != 64 or
                any(ch not in string.hexdigits for ch in value)):
            raise ValueError("SCHOOL_TELEMETRY_SOURCE_PROVENANCE_REQUIRED:" + key)
    if type(event.get("optimizer_step")) is not int:
        raise ValueError("SCHOOL_TELEMETRY_SOURCE_PROVENANCE_REQUIRED:optimizer_step")



@dataclass(frozen=True)
class ExamScore:
    grade: str
    rubric: str
    correct: int
    total: int
    step: int | None
    checkpoint_sha256: str
    generation: int
    capabilities: dict[str, tuple[int, int]]
    assessment_scope: str = ""


ExamScore.__module__ = "bilqis_mlx.presentation.school_telemetry"
