"""Small source-oracled B connective replay during candidate admission."""
from __future__ import annotations

import json
from pathlib import Path

from .generated_assessment import make_cohort
from .grade_b_oracle import evaluate as grade_b_gold, operand_truth


CAPABILITIES = ("B.OR", "B.XOR")
TRUTH_PATTERNS = (
    (False, False),
    (False, True),
    (True, False),
    (True, True),
)


def _pattern_gold(capability: str, pattern: tuple[bool, bool]) -> str:
    if capability == "B.OR":
        value = pattern[0] or pattern[1]
    elif capability == "B.XOR":
        value = pattern[0] != pattern[1]
    else:
        raise ValueError("FRAGILE_PRESERVATION_UNKNOWN_CAPABILITY")
    return "TRUE" if value else "FALSE"


def select_preservation_rows(rows, *, capabilities=CAPABILITIES,
                             excluded_ids=frozenset()) -> tuple[dict, ...]:
    """Pick fresh source siblings that cover each fragile truth-table cell once.

    Fixed examination identities are explicitly excluded. The rehearsal signal
    therefore teaches the same Boolean semantics without turning admission
    questions into lesson material.
    """
    requested = tuple(capabilities)
    if (not requested or len(requested) != len(set(requested)) or
            any(capability not in CAPABILITIES for capability in requested)):
        raise ValueError("FRAGILE_PRESERVATION_INVALID_CAPABILITY_SET")
    excluded = set(excluded_ids)
    selected = {}
    for row in rows:
        capability = row.get("capability")
        if capability not in requested or row.get("id") in excluded:
            continue
        raw = row.get("operand_truths")
        if (not isinstance(raw, (list, tuple)) or len(raw) != 2 or
                any(type(value) is not bool for value in raw)):
            raise ValueError("FRAGILE_PRESERVATION_OPERAND_PATTERN_INVALID")
        pattern = tuple(raw)
        if pattern not in TRUTH_PATTERNS or row.get("gold") != _pattern_gold(
                capability, pattern):
            raise ValueError("FRAGILE_PRESERVATION_SOURCE_GOLD_DRIFT")
        if not row.get("tokens"):
            raise ValueError("FRAGILE_PRESERVATION_SOURCE_TOKENS_MISSING")
        selected.setdefault((capability, pattern), row)
    required = {(capability, pattern)
                for capability in requested for pattern in TRUTH_PATTERNS}
    missing = required - set(selected)
    if missing:
        raise ValueError("FRAGILE_PRESERVATION_INCOMPLETE_TRUTH_TABLE")
    return tuple(selected[key] for key in sorted(selected)
                 if key in required)


def load_replay_rows(run_dir: Path, receipt: dict) -> tuple[dict, ...]:
    """Reuse the current materialized full-exam B cases, never generate new gold."""
    exam = receipt.get("last_exam") or {}
    scores = exam.get("scores") or {}
    if any(name not in scores for name in CAPABILITIES):
        return ()
    sha = exam.get("cohort_sha256")
    if (not isinstance(sha, str) or len(sha) != 64 or
            any(c not in "0123456789abcdef" for c in sha) or
            exam.get("cohort_file") != f"cohorts/{sha}.json"):
        raise ValueError("FRAGILE_REPLAY_UNBOUND_EXAM_COHORT")
    file = Path(run_dir) / "cohorts" / f"{sha}.json"
    if file.parent.is_symlink() or file.is_symlink() or not file.is_file():
        raise ValueError("FRAGILE_REPLAY_UNSAFE_COHORT_PATH")
    stored = json.loads(file.read_text(encoding="utf-8"))
    if stored.get("cohort_sha256") != sha:
        raise ValueError("FRAGILE_REPLAY_COHORT_IDENTITY_DRIFT")
    cohort = make_cohort(stored["rows"], generator_version=stored["generator_version"],
                         seed=stored["seed"], rubric_version=stored["schema"])
    if cohort.digest != sha:
        raise ValueError("FRAGILE_REPLAY_COHORT_CONTENT_DRIFT")
    rows = tuple(row for row in cohort.rows if row["capability"] in CAPABILITIES)
    if len(rows) != 24 or len({row["id"] for row in rows}) != 24:
        raise ValueError("FRAGILE_REPLAY_INCOMPLETE_B_COHORT")
    for name in CAPABILITIES:
        group = [row for row in rows if row["capability"] == name]
        if (len(group) != 12 or
                scores[name].get("total") != 12 or
                sum(row["gold"] == "TRUE" for row in group) != 6 or
                sum(row["gold"] == "FALSE" for row in group) != 6):
            raise ValueError("FRAGILE_REPLAY_UNBALANCED_B_COHORT")
        for row in group:
            args = row["record"]["query"]["args"]
            pattern = [operand_truth(row["record"]["world"], arg) for arg in args]
            if (row.get("operand_truths") != pattern or
                    grade_b_gold(row["record"], name) != row["gold"] or
                    not row.get("tokens")):
                raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
    return rows


def screen_replay(rows: tuple[dict, ...], parent: dict[str, str],
                  candidate: dict[str, str], cohort_sha: str) -> dict:
    """A fixed row lost by a challenger cannot be offset by a different gain."""
    required = {row["id"] for row in rows}
    if required - parent.keys() or required - candidate.keys():
        raise ValueError("FRAGILE_REPLAY_MISSING_PAIRED_PREDICTION")
    lost = []
    repaired = 0
    for row in rows:
        old, new, gold = parent[row["id"]], candidate[row["id"]], row["gold"]
        if old not in ("TRUE", "FALSE") or new not in ("TRUE", "FALSE"):
            raise ValueError("FRAGILE_REPLAY_INVALID_PREDICTION")
        if old == gold and new != gold:
            lost.append({"id": row["id"], "capability": row["capability"]})
        elif old != gold and new == gold:
            repaired += 1
    return {"status": "MEASURED", "cohort_sha256": cohort_sha,
            "rows": len(rows), "regressions": lost, "repaired": repaired}
