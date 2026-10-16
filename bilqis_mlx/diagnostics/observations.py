"""Reconstruct independently checkable binary predictions from saved exam gold/misses.

Historical source cohorts and their *actual recorded misses* are read-only;
unobserved future multi-class predictions must be reported NOT_MEASURED.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import json

from ..generated_assessment import make_cohort


@dataclass(frozen=True)
class CapabilityObservation:
    capability: str
    correct: int
    total: int
    gold_false: int
    gold_true: int
    predicted_false: int
    predicted_true: int
    confusion_ff: int
    confusion_ft: int
    confusion_tf: int
    confusion_tt: int

    @property
    def constant_prediction(self) -> bool:
        return self.total > 1 and (self.predicted_false == self.total or
                                    self.predicted_true == self.total)

    @property
    def mixed_gold(self) -> bool:
        return self.gold_false > 0 and self.gold_true > 0

    @property
    def majority_baseline(self) -> int:
        return max(self.gold_false, self.gold_true)


@dataclass(frozen=True)
class ExamObservation:
    cohort_sha256: str
    student_sha256: str
    optimizer_step: int
    rubric_sha256: str
    generator_version: str
    capabilities: tuple[CapabilityObservation, ...]

    def grade(self, letter: str) -> tuple[CapabilityObservation, ...]:
        return tuple(c for c in self.capabilities if c.capability.split(".", 1)[0] == letter)

    def grade_total(self, letter: str) -> CapabilityObservation:
        """A grade's observed confusion, not a new semantic capability ID."""
        group = self.grade(letter)
        if not group:
            raise ValueError("DIAGNOSTIC_GRADE_NOT_OBSERVED")
        fields = ("correct", "total", "gold_false", "gold_true",
                  "predicted_false", "predicted_true", "confusion_ff",
                  "confusion_ft", "confusion_tf", "confusion_tt")
        return CapabilityObservation(letter, *(sum(getattr(c, field) for c in group)
                                              for field in fields))


def observe_binary_exam(cohort: dict, last_exam: dict) -> ExamObservation:
    """Fail closed on imperfect source custody; no inference or teacher mutation.

    The scorer's saved `misses_for_teacher` contains all wrong predictions and
    their gold labels. Missing IDs are correct *only* after score validation.
    Never reconstruct a nonbinary label from absence in the missed-row list.
    """
    if (cohort.get("cohort_sha256") != last_exam.get("cohort_sha256") or
            cohort.get("seed") != last_exam.get("cohort_seed") or
            cohort.get("generator_version") != last_exam.get("generator_version") or
            cohort.get("rubric_sha256") != last_exam.get("exam_rubric_sha256") or
            not last_exam.get("student_sha256") or
            type(last_exam.get("optimizer_step")) is not int):
        raise ValueError("DIAGNOSTIC_EXAM_CUSTODY_MISMATCH")
    rows = cohort.get("rows")
    if not isinstance(rows, list):
        raise ValueError("DIAGNOSTIC_COHORT_ROWS_MISSING")
    candidate = make_cohort(rows, generator_version=cohort["generator_version"],
                            seed=cohort["seed"], rubric_version=cohort["schema"])
    if candidate.digest != cohort["cohort_sha256"]:
        raise ValueError("DIAGNOSTIC_COHORT_CONTENT_DRIFT")
    if any(r.get("answer_kind") != "binary" or r.get("gold") not in ("TRUE", "FALSE")
           for r in rows):
        raise ValueError("DIAGNOSTIC_UNSUPPORTED_PREDICTION_CASTE")
    ordered = {r["id"]: r for r in rows}
    failures = last_exam.get("misses_for_teacher")
    if not isinstance(failures, list):
        raise ValueError("DIAGNOSTIC_INCOMPLETE_PREDICTION_EVIDENCE")
    by_miss = {}
    for failed in failures:
        source_row = ordered.get(failed.get("id"))
        if (source_row is None or failed["id"] in by_miss or
                failed.get("source_id") != source_row.get("source_id", source_row["id"]) or
                failed.get("capability") != source_row["capability"] or
                failed.get("gold") != source_row["gold"] or
                failed.get("predicted") not in ("TRUE", "FALSE") or
                failed["predicted"] == failed["gold"]):
            raise ValueError("DIAGNOSTIC_MISS_EVIDENCE_DRIFT")
        by_miss[failed["id"]] = failed["predicted"]
    scores = last_exam.get("scores", {})
    capabilities = []
    for name in sorted(set(r["capability"] for r in rows)):
        own = [r for r in rows if r["capability"] == name]
        matrix = Counter((r["gold"], by_miss.get(r["id"], r["gold"])) for r in own)
        correct = matrix[("FALSE", "FALSE")] + matrix[("TRUE", "TRUE")]
        if scores.get(name) != {"correct": correct, "total": len(own)}:
            raise ValueError("DIAGNOSTIC_SCORE_EVIDENCE_DRIFT:" + name)
        capabilities.append(CapabilityObservation(
            name, correct, len(own),
            matrix[("FALSE", "FALSE")] + matrix[("FALSE", "TRUE")],
            matrix[("TRUE", "FALSE")] + matrix[("TRUE", "TRUE")],
            matrix[("FALSE", "FALSE")] + matrix[("TRUE", "FALSE")],
            matrix[("FALSE", "TRUE")] + matrix[("TRUE", "TRUE")],
            matrix[("FALSE", "FALSE")], matrix[("FALSE", "TRUE")],
            matrix[("TRUE", "FALSE")], matrix[("TRUE", "TRUE")],
        ))
    return ExamObservation(cohort["cohort_sha256"], last_exam["student_sha256"],
                           last_exam["optimizer_step"], cohort["rubric_sha256"],
                           cohort["generator_version"], tuple(capabilities))


def load_saved_exam(run_dir: Path, *, state_file: Path | None = None) -> ExamObservation:
    """Read existing immutable run files without model import or writes."""
    root = Path(run_dir).resolve(strict=True)
    path = Path(state_file) if state_file is not None else root / "state.json"
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("DIAGNOSTIC_STATE_OUTSIDE_RUN")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    exam = receipt.get("last_exam")
    if not isinstance(exam, dict):
        raise ValueError("DIAGNOSTIC_EXAM_NOT_MEASURED")
    relative = Path(exam.get("cohort_file", ""))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("DIAGNOSTIC_COHORT_OUTSIDE_RUN")
    cohort_file = (root / relative).resolve(strict=True)
    if not cohort_file.is_relative_to(root / "cohorts"):
        raise ValueError("DIAGNOSTIC_COHORT_OUTSIDE_RUN")
    return observe_binary_exam(json.loads(cohort_file.read_text(encoding="utf-8")), exam)


def load_archived_exam_history(run_dir: Path, *, grade: str = "B") -> tuple[ExamObservation, ...]:
    """Read each committed exam through immutable event→state→cohort custody.

    This is an audit of saved observations. It does not load, rescore, optimize
    or reinterpret any neural weights, and makes no training-readiness claim.
    """
    root = Path(run_dir).resolve(strict=True)
    observations = []
    seen = set()
    for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("event") not in ("GRADE_A_LIVE_EXAM_COMMITTED",
                                      "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED"):
            continue
        if event.get("grade") != grade:
            continue
        generation = event.get("generation")
        if type(generation) is not int or generation < 0 or generation in seen:
            raise ValueError("DIAGNOSTIC_EVENT_GENERATION_DRIFT")
        seen.add(generation)
        saved = root / "states" / f"{generation:07d}.json"
        obs = load_saved_exam(root, state_file=saved)
        if (obs.cohort_sha256 != event.get("cohort_sha256") or
                obs.student_sha256 != event.get("student_sha256") or
                obs.optimizer_step != event.get("optimizer_step") or
                obs.rubric_sha256 != event.get("rubric") or
                {cap.capability: {"correct": cap.correct, "total": cap.total}
                 for cap in obs.capabilities} != event.get("scores")):
            raise ValueError("DIAGNOSTIC_EVENT_STATE_CONFLICT")
        observations.append(obs)
    return tuple(observations)
