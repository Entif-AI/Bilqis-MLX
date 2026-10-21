"""Source-backed history preselection keeps live diagnostics exact and bounded."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.diagnostics.exam_events import _comparable_history
from bilqis_mlx.diagnostics.observations import (
    _cached_history_bucket,
    distinct_checkpoint_history,
    load_archived_exam_history,
    load_saved_exam,
)
from bilqis_mlx.diagnostics.signals import diagnose_history
from bilqis_mlx.generated_assessment import make_cohort, score


RUBRIC = "a" * 64
GENERATOR = "fixture/current-v1"
SOURCE = "b" * 64
GENERATOR_CODE = "c" * 64
SCOPE = "d" * 64


def _save_exam(root: Path, generation: int, *, rubric: str = RUBRIC,
               generator: str = GENERATOR, seed: int | None = None) -> dict:
    seed = generation if seed is None else seed
    rows = [
        {
            "id": f"row-{seed}-{index}",
            "source_id": f"row-{seed}-{index}",
            "capability": "B.AND",
            "answer_kind": "binary",
            "gold": "TRUE" if index % 2 else "FALSE",
        }
        for index in range(12)
    ]
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed,
        rubric_version="history-preselection-fixture/v1")
    cohort_payload = {
        "schema": cohort.rubric_version,
        "rubric_sha256": rubric,
        "generator_version": cohort.generator_version,
        "generator_code_sha256": GENERATOR_CODE,
        "source_manifest_sha256": SOURCE,
        "seed": cohort.seed,
        "cohort_sha256": cohort.digest,
        "rows": rows,
    }
    student_sha = f"{generation:064x}"
    checkpoint = {
        "sha256": student_sha,
        "optimizer_step": 100 + generation,
        "model_and_native_adamw": True,
    }
    measured = score(
        cohort, {row["id"]: "FALSE" for row in rows}, checkpoint)
    exam = {
        "cohort_sha256": cohort.digest,
        "cohort_file": f"cohorts/{cohort.digest}.json",
        "cohort_seed": seed,
        "generator_version": generator,
        "exam_rubric_sha256": rubric,
        "assessment_scope_sha256": SCOPE,
        "student_sha256": student_sha,
        "optimizer_step": checkpoint["optimizer_step"],
        "scores": measured["scores"],
        "misses_for_teacher": list(measured["misses_for_teacher"]),
    }
    receipt = {
        "generation": generation,
        "run_id": "history-preselection-run",
        "last_exam": exam,
    }
    event = {
        "event": "SCHOOL_LIVE_EXAM_COMMITTED",
        "grade": "B",
        "generation": generation,
        "rubric": rubric,
        "generator_version": generator,
        "cohort_sha256": cohort.digest,
        "student_sha256": student_sha,
        "optimizer_step": checkpoint["optimizer_step"],
        "scores": measured["scores"],
    }
    (root / "states").mkdir(exist_ok=True)
    (root / "cohorts").mkdir(exist_ok=True)
    (root / exam["cohort_file"]).write_text(
        json.dumps(cohort_payload), encoding="utf-8")
    (root / "states" / f"{generation:07d}.json").write_text(
        json.dumps(receipt), encoding="utf-8")
    with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")
    return receipt


def _append_invalid_state_event(root: Path, generation: int, *,
                                rubric: str | None = RUBRIC,
                                generator: str | None = GENERATOR) -> None:
    event = {
        "event": "SCHOOL_LIVE_EXAM_COMMITTED",
        "grade": "B",
        "generation": generation,
        "cohort_sha256": "e" * 64,
        "student_sha256": f"{generation:064x}",
        "optimizer_step": 100 + generation,
        "scores": {"B.AND": {"correct": 1, "total": 1}},
    }
    if rubric is not None:
        event["rubric"] = rubric
    if generator is not None:
        event["generator_version"] = generator
    # Valid JSON, wrong immutable generation: selected verification must fail.
    (root / "states" / f"{generation:07d}.json").write_text(
        json.dumps({"generation": generation + 1000}), encoding="utf-8")
    with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")


class HistoryPreselectionTests(unittest.TestCase):
    def setUp(self):
        _cached_history_bucket.cache_clear()

    def test_live_comparison_skips_proven_unrelated_invalid_state_but_full_audit_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _save_exam(root, 1)
            current = _save_exam(root, 2)
            observed = load_saved_exam(
                root, state_file=root / "states" / "0000002.json")
            before, issue = _comparable_history(root, observed)
            self.assertIsNone(issue)
            before_findings = diagnose_history(
                distinct_checkpoint_history((*before, observed)))

            _append_invalid_state_event(
                root, 3, rubric="f" * 64, generator="fixture/obsolete-v1")

            after, issue = _comparable_history(root, observed)
            self.assertIsNone(issue)
            self.assertEqual(after, before)
            self.assertEqual(
                diagnose_history(distinct_checkpoint_history((*after, observed))),
                before_findings)
            with self.assertRaisesRegex(ValueError, "STATE_GENERATION_DRIFT"):
                load_archived_exam_history(root, grade=None)

    def test_matching_invalid_state_fails_filtered_live_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            current = _save_exam(root, 1)
            observed = load_saved_exam(
                root, state_file=root / "states" / "0000001.json")
            _append_invalid_state_event(root, 2)

            history, issue = _comparable_history(root, observed)
            self.assertEqual(history, ())
            self.assertIn("STATE_GENERATION_DRIFT", issue)
            with self.assertRaisesRegex(ValueError, "STATE_GENERATION_DRIFT"):
                load_archived_exam_history(
                    root, grade=None, rubric_sha256=RUBRIC,
                    generator_version=GENERATOR)

    def test_unknown_header_metadata_is_not_silently_filtered(self):
        for missing in ("rubric", "generator"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                _save_exam(root, 1)
                observed = load_saved_exam(
                    root, state_file=root / "states" / "0000001.json")
                _append_invalid_state_event(
                    root, 2,
                    rubric=None if missing == "rubric" else RUBRIC,
                    generator=None if missing == "generator" else GENERATOR)

                history, issue = _comparable_history(root, observed)
                self.assertEqual(history, ())
                self.assertIn("STATE_GENERATION_DRIFT", issue)

    def test_incremental_cache_is_keyed_by_rubric_and_generator_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _save_exam(root, 1, rubric=RUBRIC, generator=GENERATOR)
            other_rubric = "9" * 64
            other_generator = "fixture/other-v1"
            _save_exam(
                root, 2, rubric=other_rubric, generator=other_generator)

            current = load_archived_exam_history(
                root, grade=None, incremental=True,
                rubric_sha256=RUBRIC, generator_version=GENERATOR)
            other = load_archived_exam_history(
                root, grade=None, incremental=True,
                rubric_sha256=other_rubric, generator_version=other_generator)

            self.assertEqual([item.optimizer_step for item in current], [101])
            self.assertEqual([item.optimizer_step for item in other], [102])
            self.assertEqual(len(load_archived_exam_history(root, grade=None)), 2)

    def test_incremental_filter_still_hashes_skipped_ledger_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _save_exam(root, 1)
            _append_invalid_state_event(
                root, 2, rubric="f" * 64, generator="fixture/obsolete-v1")
            first = load_archived_exam_history(
                root, grade=None, incremental=True,
                rubric_sha256=RUBRIC, generator_version=GENERATOR)
            self.assertEqual([item.optimizer_step for item in first], [101])

            events = [json.loads(line) for line in
                      (root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            events[-1]["rubric"] = RUBRIC
            events[-1]["generator_version"] = GENERATOR
            (root / "events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "STATE_GENERATION_DRIFT"):
                load_archived_exam_history(
                    root, grade=None, incremental=True,
                    rubric_sha256=RUBRIC, generator_version=GENERATOR)


if __name__ == "__main__":
    unittest.main()
