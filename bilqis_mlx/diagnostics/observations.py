"""Reconstruct source-scored exam observations from saved gold and misses.

Historical source cohorts and their *actual recorded misses* are read-only;
unobserved answer classes and absent prediction evidence remain NOT_MEASURED.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from functools import lru_cache
import hashlib
from pathlib import Path
import json
import os
import stat

from ..generated_assessment import make_cohort


def _require_evidence_file(root: Path, path: Path) -> Path:
    """The named run's evidence must be regular files, with no redirected parents."""
    if not path.is_relative_to(root):
        raise ValueError("DIAGNOSTIC_EVIDENCE_NOT_REGULAR")
    cursor = root
    for part in path.relative_to(root).parts:
        cursor = cursor / part
        if part == ".." or cursor.is_symlink():
            raise ValueError("DIAGNOSTIC_EVIDENCE_NOT_REGULAR")
    if not path.is_file():
        raise ValueError("DIAGNOSTIC_EVIDENCE_NOT_REGULAR")
    return path


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
    component_majority_baseline: int | None = None
    component_classes_measured: bool = True
    gold_counts: tuple[tuple[str, int], ...] = ()
    prediction_counts: tuple[tuple[str, int], ...] = ()

    @property
    def constant_prediction(self) -> bool:
        if self.prediction_counts:
            return self.total > 1 and max(dict(self.prediction_counts).values()) == self.total
        return self.total > 1 and (self.predicted_false == self.total or
                                    self.predicted_true == self.total)

    @property
    def mixed_gold(self) -> bool:
        if self.gold_counts:
            return len(self.gold_counts) > 1
        return self.gold_false > 0 and self.gold_true > 0

    @property
    def majority_baseline(self) -> int:
        return (self.component_majority_baseline if self.component_majority_baseline is not None
                else max(dict(self.gold_counts).values()) if self.gold_counts
                else max(self.gold_false, self.gold_true))

    @property
    def baseline_measured(self) -> bool:
        return self.mixed_gold and self.component_classes_measured


def aggregate_capabilities(name: str, group: tuple[CapabilityObservation, ...]) -> CapabilityObservation:
    """Retain capability-conditioned baselines when pooling prediction counts."""
    fields = ("correct", "total", "gold_false", "gold_true", "predicted_false",
              "predicted_true", "confusion_ff", "confusion_ft", "confusion_tf", "confusion_tt")
    gold, predictions = Counter(), Counter()
    for cap in group:
        gold.update(dict(cap.gold_counts) if cap.gold_counts else
                    {"FALSE": cap.gold_false, "TRUE": cap.gold_true})
        predictions.update(dict(cap.prediction_counts) if cap.prediction_counts else
                    {"FALSE": cap.predicted_false, "TRUE": cap.predicted_true})
    return CapabilityObservation(name, *(sum(getattr(c, field) for c in group) for field in fields),
        component_majority_baseline=sum(c.majority_baseline for c in group),
        component_classes_measured=all(c.baseline_measured for c in group),
        gold_counts=tuple(sorted((k,v) for k,v in gold.items() if v)),
        prediction_counts=tuple(sorted((k,v) for k,v in predictions.items() if v)))


@dataclass(frozen=True)
class ExamObservation:
    cohort_sha256: str
    student_sha256: str
    optimizer_step: int
    rubric_sha256: str
    generator_version: str
    capabilities: tuple[CapabilityObservation, ...]
    source_manifest_sha256: str = ""
    generator_code_sha256: str = ""
    event_outbox_verified: bool = False
    run_id: str = ""
    assessment_scope_sha256: str = ""
    lineage_id: str = ""

    @property
    def inventory(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted((c.capability, c.total) for c in self.capabilities))

    @property
    def contract(self) -> tuple[str, ...]:
        return (self.rubric_sha256, self.generator_version,
                self.source_manifest_sha256, self.generator_code_sha256,
                self.assessment_scope_sha256)

    def grade(self, letter: str) -> tuple[CapabilityObservation, ...]:
        return tuple(c for c in self.capabilities if c.capability.split(".", 1)[0] == letter)

    def grade_total(self, letter: str) -> CapabilityObservation:
        """A grade's observed confusion, not a new semantic capability ID."""
        group = self.grade(letter)
        if not group:
            raise ValueError("DIAGNOSTIC_GRADE_NOT_OBSERVED")
        return aggregate_capabilities(letter, group)


def observe_exam(cohort: dict, last_exam: dict) -> ExamObservation:
    """Fail closed on imperfect source custody; no inference or teacher mutation.

    The scorer's saved `misses_for_teacher` contains all wrong predictions and
    their gold labels. Missing IDs are correct *only* after score validation.
    Never reconstruct a nonbinary label from absence in the missed-row list.
    """
    def is_sha(value):
        return (isinstance(value, str) and len(value) == 64 and
                all(c in "0123456789abcdef" for c in value))

    if (not isinstance(cohort, dict) or not isinstance(last_exam, dict) or
            not all(is_sha(last_exam.get(key)) for key in (
                "cohort_sha256", "student_sha256", "exam_rubric_sha256")) or
            not cohort.get("schema") or not cohort.get("generator_version") or
            type(cohort.get("seed")) is not int or
            cohort.get("cohort_sha256") != last_exam.get("cohort_sha256") or
            cohort.get("seed") != last_exam.get("cohort_seed") or
            cohort.get("generator_version") != last_exam.get("generator_version") or
            cohort.get("rubric_sha256") != last_exam.get("exam_rubric_sha256") or
            type(last_exam.get("optimizer_step")) is not int or
            last_exam["optimizer_step"] < 0):
        raise ValueError("DIAGNOSTIC_EXAM_CUSTODY_MISMATCH")
    rows = cohort.get("rows")
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        raise ValueError("DIAGNOSTIC_COHORT_ROWS_MISSING")
    candidate = make_cohort(rows, generator_version=cohort["generator_version"],
                            seed=cohort["seed"], rubric_version=cohort["schema"])
    if candidate.digest != cohort["cohort_sha256"]:
        raise ValueError("DIAGNOSTIC_COHORT_CONTENT_DRIFT")
    if any(not ((r.get("answer_kind") == "binary" and r.get("gold") in ("TRUE", "FALSE")) or
               (r.get("answer_kind") == "numeric_active" and isinstance(r.get("gold"), str)
                and r["gold"].isascii() and r["gold"].isdecimal())) for r in rows):
        raise ValueError("DIAGNOSTIC_UNSUPPORTED_PREDICTION_CASTE")
    ordered = {r["id"]: r for r in rows}
    failures = last_exam.get("misses_for_teacher")
    if not isinstance(failures, list):
        raise ValueError("DIAGNOSTIC_INCOMPLETE_PREDICTION_EVIDENCE")
    by_miss = {}
    for failed in failures:
        if not isinstance(failed, dict):
            raise ValueError("DIAGNOSTIC_MISS_EVIDENCE_DRIFT")
        source_row = ordered.get(failed.get("id"))
        if (source_row is None or failed["id"] in by_miss or
                failed.get("source_id") != source_row.get("source_id", source_row["id"]) or
                failed.get("capability") != source_row["capability"] or
                failed.get("gold") != source_row["gold"] or
                not isinstance(failed.get("predicted"), str) or not failed["predicted"] or
                (source_row["answer_kind"] == "binary" and failed["predicted"] not in ("TRUE", "FALSE")) or
                failed["predicted"] == failed["gold"]):
            raise ValueError("DIAGNOSTIC_MISS_EVIDENCE_DRIFT")
        by_miss[failed["id"]] = failed["predicted"]
    scores = last_exam.get("scores", {})
    names = {r["capability"] for r in rows}
    if not isinstance(scores, dict) or set(scores) != names:
        raise ValueError("DIAGNOSTIC_SCORE_EVIDENCE_DRIFT")
    capabilities = []
    for name in sorted(names):
        own = [r for r in rows if r["capability"] == name]
        matrix = Counter((r["gold"], by_miss.get(r["id"], r["gold"])) for r in own)
        correct = sum(count for (gold, predicted), count in matrix.items() if gold == predicted)
        gold_counts = Counter(r["gold"] for r in own)
        prediction_counts = Counter(by_miss.get(r["id"], r["gold"]) for r in own)
        kinds = {kind: Counter(r["gold"] for r in own if r["answer_kind"] == kind)
                 for kind in {r["answer_kind"] for r in own}}
        stated = scores[name]
        if (not isinstance(stated, dict) or
                any(type(stated.get(key)) is not int for key in ("correct", "total")) or
                stated != {"correct": correct, "total": len(own)}):
            raise ValueError("DIAGNOSTIC_SCORE_EVIDENCE_DRIFT:" + name)
        capabilities.append(CapabilityObservation(
            name, correct, len(own),
            matrix[("FALSE", "FALSE")] + matrix[("FALSE", "TRUE")],
            matrix[("TRUE", "FALSE")] + matrix[("TRUE", "TRUE")],
            matrix[("FALSE", "FALSE")] + matrix[("TRUE", "FALSE")],
            matrix[("FALSE", "TRUE")] + matrix[("TRUE", "TRUE")],
            matrix[("FALSE", "FALSE")], matrix[("FALSE", "TRUE")],
            matrix[("TRUE", "FALSE")], matrix[("TRUE", "TRUE")],
            component_majority_baseline=sum(max(counts.values()) for counts in kinds.values()),
            component_classes_measured=all(len(counts) > 1 for counts in kinds.values()),
            gold_counts=tuple(sorted(gold_counts.items())),
            prediction_counts=tuple(sorted(prediction_counts.items())),
        ))
    return ExamObservation(cohort["cohort_sha256"], last_exam["student_sha256"],
                           last_exam["optimizer_step"], cohort["rubric_sha256"],
                           cohort["generator_version"], tuple(capabilities),
                           cohort.get("source_manifest_sha256", ""),
                           cohort.get("generator_code_sha256", ""),
                           assessment_scope_sha256=last_exam.get("assessment_scope_sha256", ""))


def observe_binary_exam(cohort: dict, last_exam: dict) -> ExamObservation:
    """Compatibility API for archived binary-only evaluation contracts."""
    if any(r.get("answer_kind") != "binary" for r in cohort.get("rows", ())):
        raise ValueError("DIAGNOSTIC_UNSUPPORTED_PREDICTION_CASTE")
    return observe_exam(cohort, last_exam)


def _require_run_id(receipt: dict) -> str:
    run_id = receipt.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("DIAGNOSTIC_STATE_RUN_ID_MISSING")
    return run_id


def load_saved_exam(run_dir: Path, *, state_file: Path | None = None) -> ExamObservation:
    """Read existing immutable run files without model import or writes."""
    root = Path(run_dir).resolve(strict=True)
    path = Path(state_file) if state_file is not None else root / "state.json"
    if not path.resolve().is_relative_to(root):
        raise ValueError("DIAGNOSTIC_STATE_OUTSIDE_RUN")
    archived_generation = path.parent == root / "states" and path.suffix == ".json"
    if archived_generation:
        from ..state_archive import read_generation
        if not path.stem.isdecimal():
            raise ValueError("DIAGNOSTIC_STATE_GENERATION_DRIFT")
        try:
            receipt = read_generation(root, int(path.stem))
        except ValueError as exc:
            # Preserve the diagnostic contract when a generation is stored
            # in the new verified compression format.
            if str(exc).startswith("STATE_ARCHIVE_SYMLINK_FORBIDDEN"):
                raise ValueError("DIAGNOSTIC_EVIDENCE_NOT_REGULAR") from exc
            if str(exc) == "STATE_ARCHIVE_GENERATION_DRIFT":
                raise ValueError("DIAGNOSTIC_STATE_GENERATION_DRIFT") from exc
            raise
    else:
        _require_evidence_file(root, path)
        receipt = json.loads(path.read_text(encoding="utf-8"))
    exam = receipt.get("last_exam")
    if not isinstance(exam, dict):
        raise ValueError("DIAGNOSTIC_EXAM_NOT_MEASURED")
    relative = Path(exam.get("cohort_file", ""))
    if (relative.as_posix() != "cohorts/" + str(exam.get("cohort_sha256")) + ".json" or
            relative.is_absolute() or ".." in relative.parts):
        raise ValueError("DIAGNOSTIC_COHORT_OUTSIDE_RUN")
    cohort_file = _require_evidence_file(root, root / relative).resolve(strict=True)
    if not cohort_file.is_relative_to(root / "cohorts"):
        raise ValueError("DIAGNOSTIC_COHORT_OUTSIDE_RUN")
    if path.parent == root / "states":
        generation = receipt.get("generation")
        if (type(generation) is not int or generation < 0 or
                path.name != f"{generation:07d}.json"):
            raise ValueError("DIAGNOSTIC_STATE_GENERATION_DRIFT")
    run_id = _require_run_id(receipt)
    return replace(observe_exam(
        json.loads(cohort_file.read_text(encoding="utf-8")), exam),
        run_id=run_id, lineage_id=_receipt_lineage_id(receipt))


def _receipt_lineage_id(receipt: dict) -> str:
    """Identify the active optimizer lineage without rewriting history.

    Normal training stays on the run root. An explicit experimental baseline
    rebase starts a new immutable branch whose saved receipts carry the exact
    rebase provenance forward. Diagnostics may compare checkpoints inside one
    branch, but a lower optimizer step across a certified rebase is not data
    corruption and must not poison all later learning-history observations.
    """
    run_id = _require_run_id(receipt)
    rebased = receipt.get("experimental_baseline_rebase")
    if rebased is None:
        return "run-root/" + run_id
    if (not isinstance(rebased, dict) or
            rebased.get("schema") != "bilqis.mlx.experimental-baseline-rebase/v1" or
            type(rebased.get("source_state_generation")) is not int or
            type(rebased.get("prior_experiment_generation")) is not int or
            type(rebased.get("baseline_optimizer_step")) is not int or
            not isinstance(rebased.get("baseline_sha256"), str) or
            len(rebased["baseline_sha256"]) != 64):
        raise ValueError("DIAGNOSTIC_EXPERIMENT_REBASE_RECEIPT_DRIFT")
    identity = {
        "run_id": run_id,
        "source_state_generation": rebased["source_state_generation"],
        "prior_experiment_generation": rebased["prior_experiment_generation"],
        "baseline_sha256": rebased["baseline_sha256"],
        "baseline_optimizer_step": rebased["baseline_optimizer_step"],
    }
    return "experiment-rebase/" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass
class _HistoryCache:
    """In-process witness for already verified immutable source observations."""
    offset: int = 0
    ledger_hash: str = ""
    ledger_inode: tuple[int, int] | None = None
    last_generation: int = -1
    observations: tuple[ExamObservation, ...] = ()
    files: dict[Path, tuple[int, ...]] = field(default_factory=dict)


@lru_cache(maxsize=2)
def _cached_history_bucket(root: str, grade: str | None) -> _HistoryCache:
    return _HistoryCache()


def _file_signature(path: Path) -> tuple[int, ...]:
    """Detect source replacement, in-place edits and archive retirement."""
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.parent.is_symlink():
        raise ValueError("DIAGNOSTIC_CACHED_EVIDENCE_UNSAFE_PATH")
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _history_evidence_files(root: Path, generation: int,
                            observation: ExamObservation) -> tuple[Path, ...]:
    stem = root / "states" / f"{generation:07d}.json"
    archived = (stem.with_name(stem.name + ".gz"),
                stem.with_name(stem.name + ".sha256"))
    return (stem if stem.is_file() or stem.is_symlink() else archived[0],
            *(() if stem.is_file() or stem.is_symlink() else (archived[1],)),
            root / "cohorts" / f"{observation.cohort_sha256}.json")


def _history_delta(ledger: Path, cache: _HistoryCache | None):
    """Hash the complete ledger prefix, then parse only the newly appended tail."""
    digest = hashlib.sha256()
    with ledger.open("rb") as stream:
        info = os.fstat(stream.fileno())
        inode = (info.st_dev, info.st_ino)
        offset = cache.offset if cache and cache.ledger_inode == inode else 0
        remaining = offset
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                return None
            digest.update(chunk)
            remaining -= len(chunk)
        if cache and offset != cache.offset:
            return None
        if cache and digest.hexdigest() != cache.ledger_hash:
            return None
        tail = stream.read()
    if tail and not tail.endswith(b"\n"):
        raise ValueError("DIAGNOSTIC_EVENT_INCOMPLETE_LINE")
    digest.update(tail)
    return tail.splitlines(), offset + len(tail), digest.hexdigest(), inode


def _require_checkpoint_progression(step: int, student_sha: str,
                                    previous_step: int, previous_sha: str | None):
    if step < previous_step:
        raise ValueError("DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY")
    if step == previous_step and student_sha != previous_sha:
        raise ValueError("DIAGNOSTIC_SAME_STEP_CHECKPOINT_CONFLICT")


def _append_verified_exams(root: Path, lines, grade, observations, files,
                           last_generation: int = -1):
    run_id = observations[-1].run_id if observations else None
    last_step = observations[-1].optimizer_step if observations else -1
    last_student_sha = observations[-1].student_sha256 if observations else None
    last_lineage = observations[-1].lineage_id if observations else None
    # Generation remains a separate event identity from student/checkpoint.
    # A cache stores it independently because the most recent log events need
    # not correspond to the most recent accepted optimizer step.
    for line in lines:
        event = json.loads(line)
        if event.get("event") not in ("GRADE_A_LIVE_EXAM_COMMITTED",
                                      "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "SCHOOL_LIVE_EXAM_COMMITTED"):
            continue
        if grade is not None and event.get("grade") != grade:
            continue
        generation = event.get("generation")
        if type(generation) is not int or generation < 0:
            raise ValueError("DIAGNOSTIC_EVENT_GENERATION_DRIFT")
        if generation <= last_generation:
            raise ValueError("DIAGNOSTIC_NON_MONOTONIC_EVENT_HISTORY")
        saved = root / "states" / f"{generation:07d}.json"
        obs = load_saved_exam(root, state_file=saved)
        from ..state_archive import read_generation
        receipt = read_generation(root, generation)
        if (not receipt.get("run_id") or
                (run_id is not None and receipt["run_id"] != run_id)):
            raise ValueError("DIAGNOSTIC_EVENT_RUN_CONFLICT")
        run_id = receipt["run_id"]
        if "delivery_outbox" in receipt:
            # The trainer owns generation event IDs. Reuse its pure serializer;
            # it imports no neural runtime and performs no checkpoint I/O.
            from ..trainer import _with_delivery_outbox
            outbox = receipt["delivery_outbox"]
            if not isinstance(outbox, list) or any(not isinstance(e, dict) for e in outbox):
                raise ValueError("DIAGNOSTIC_EVENT_OUTBOX_CONFLICT")
            expected = _with_delivery_outbox(receipt, tuple(
                {key: value for key, value in e.items() if key != "event_id"}
                for e in outbox))["delivery_outbox"]
            if expected != outbox or outbox.count(event) != 1:
                raise ValueError("DIAGNOSTIC_EVENT_OUTBOX_CONFLICT")
            obs = replace(obs, event_outbox_verified=True)
        if (obs.cohort_sha256 != event.get("cohort_sha256") or
                obs.student_sha256 != event.get("student_sha256") or
                obs.optimizer_step != event.get("optimizer_step") or
                obs.generator_version != event.get("generator_version") or
                obs.rubric_sha256 != event.get("rubric") or
                {cap.capability: {"correct": cap.correct, "total": cap.total}
                 for cap in obs.capabilities} != event.get("scores")):
            raise ValueError("DIAGNOSTIC_EVENT_STATE_CONFLICT")
        if last_lineage == obs.lineage_id:
            _require_checkpoint_progression(
                obs.optimizer_step, obs.student_sha256, last_step, last_student_sha)
        last_generation, last_step = generation, obs.optimizer_step
        last_student_sha = obs.student_sha256
        last_lineage = obs.lineage_id
        observations.append(obs)
        if files is not None:
            for path in _history_evidence_files(root, generation, obs):
                files[path] = _file_signature(path)
    return last_generation


def load_archived_exam_history(run_dir: Path, *, grade: str | None = "B",
                               incremental: bool = False) -> tuple[ExamObservation, ...]:
    """Validate all saved exams; optionally reuse immutable verified history.

    Standalone audits always reread full source evidence. The live observer may
    reuse already verified events *only* while the complete log prefix matches
    byte-for-byte by SHA and every referenced immutable file is unchanged.
    """
    root = Path(run_dir).resolve(strict=True)
    ledger = _require_evidence_file(root, root / "events.jsonl")
    bucket = _cached_history_bucket(str(root), grade) if incremental else None
    valid = bool(bucket and bucket.ledger_hash)
    if valid:
        try:
            valid = all(_file_signature(path) == signature
                        for path, signature in bucket.files.items())
        except (OSError, ValueError):
            valid = False
    previous = bucket if valid else None
    delta = _history_delta(ledger, previous)
    if delta is None:
        previous = None
        delta = _history_delta(ledger, None)
    lines, size, fingerprint, inode = delta
    observations = list(previous.observations) if previous else []
    files = dict(previous.files) if previous else ({} if incremental else None)
    # A source-backed audit validates the complete ledger and its provenance.
    last_generation = _append_verified_exams(
        root, lines, grade, observations, files,
        previous.last_generation if previous else -1)
    if bucket is not None:
        bucket.offset = size
        bucket.ledger_hash = fingerprint
        bucket.ledger_inode = inode
        bucket.last_generation = last_generation
        bucket.observations = tuple(observations)
        bucket.files = files
    return tuple(observations)


def distinct_checkpoint_history(history: tuple[ExamObservation, ...]) -> tuple[ExamObservation, ...]:
    """One comparable observation per intact student, retaining the latest exam.

    Every archived event must already have passed full state/cohort/outbox
    verification. This is only a projection for longitudinal analysis, never
    the raw evidence inventory or a relaxation of `diagnose_history` itself.
    """
    distinct = []
    indices = {}
    previous = None
    for observed in history:
        if previous is not None and previous.lineage_id == observed.lineage_id:
            _require_checkpoint_progression(
                observed.optimizer_step, observed.student_sha256,
                previous.optimizer_step, previous.student_sha256)
        key = (observed.lineage_id, observed.contract,
               observed.optimizer_step, observed.student_sha256)
        if key in indices:
            distinct[indices[key]] = observed
        else:
            indices[key] = len(distinct)
            distinct.append(observed)
        previous = observed
    return tuple(distinct)
