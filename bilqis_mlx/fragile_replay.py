"""Small source-oracled B connective replay during candidate admission."""
from __future__ import annotations

import json
from pathlib import Path

from .generated_assessment import make_cohort
from .grade_b_oracle import evaluate as grade_b_gold, operand_truth


CAPABILITIES = ("B.OR", "B.XOR")


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
