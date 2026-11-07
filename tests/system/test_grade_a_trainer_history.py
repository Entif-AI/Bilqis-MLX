"""Trainer contract tests: disposable toy optimization, never real student steps."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import io
import inspect
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from bilqis_mlx import trainer as trainer
from bilqis_mlx.state_dag import read_current, read_generation
from bilqis_mlx.grade_a_release import accepted_grade_a, RELEASE, AUTHORITY
from bilqis_mlx.live_grade_a import live_course, RELEASE as LIVE_RELEASE
from bilqis_mlx.trainer import (
    _make_batch, _persist, _seed, _state_from_json, _train_step,
    _take_visit, _take_exam,
    choose_lesson_batch,
    operator_lock, prepare_source,
    _initial_model, _bundle_pointer, _resume, _durable_json,
    _clean_staged_bundles, _quarantine_newer_uncommitted_bundles,
)
from bilqis_mlx.learning.learning_experiment import reserve_weakness_targets
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.source import AUDITED_PARENT
from bilqis_mlx.curriculum.scheduler import start_new, visit
from bilqis_mlx.learning.capability_frontier import promote
from tests.support.executable_school import admit_executable_school
from bilqis_mlx.diagnostics import DiagnosticStatus

ROOT = Path(__file__).resolve().parents[2] / "vendor" / "legacy-v16"
SOURCE = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
MANIFEST = Path(__file__).resolve().parents[2] / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"

def _historical_v1_receipt(*, manifest, school, base, frontier, teacher,
                           teacher_sha, provenance, config, parameters, graph,
                           answer_ids):
    semantic_graph_sha256 = __import__(
        "bilqis_mlx.trainer", fromlist=["_fingerprint"])._fingerprint(graph)
    return {
        "schema": "bilqis.mlx.human-grade-a-trainer/v1",
        "generation": 1, "run_id": "historic-disposable",
        "accepted_authority": AUTHORITY,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "teacher_source_sha256": teacher_sha,
        "school": asdict(school), "model_bundle": base.filename,
        "capability_best": frontier, "teacher": teacher,
        "teacher_provenance": provenance, "config": config,
        "parameter_shapes": {name: list(value.shape)
                             for name, value in parameters.items()},
        "semantic_graph_sha256": semantic_graph_sha256,
        "answer_ids": answer_ids, "result": "ACTIVE_GRADE_A",
        "last_exam": None,
    }

class GradeATrainerHistoryTests(unittest.TestCase):
    @unittest.skipUnless(SOURCE.is_file(), "Pinned original student unavailable")
    def test_historical_v1_resume_is_rejected_without_rewriting_history(self):
        """Historical v1 evidence remains inspectable but cannot re-enter live writers."""
        import mlx.core as mx
        mx.set_default_device(mx.cpu)
        manifest, old_course, engine, sha, teacher, provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
        course = live_course(old_course)
        parameters, optimizer, config, graph, answer_ids = _initial_model(SOURCE)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            with redirect_stdout(io.StringIO()):
                base = _bundle_pointer(run_dir, "old-v1-student", parameters,
                                       optimizer, graph, reserve_gib=0.)
            old_school = start_new(old_course, base)
            for cap in [c.id for c in old_course.grades[0].capabilities]:
                old_school = visit(old_course, old_school, cap, base)
            scores = {c.id: {"correct": 5, "total": 12}
                      for c in old_course.grades[0].capabilities}
            frontier = promote({}, scores, manifest["exam_rubric_sha256"],
                               asdict(base), "historic-evaluation",
                               tuple(sorted(scores)))
            historical = _historical_v1_receipt(
                manifest=manifest, school=old_school, base=base,
                frontier=frontier, teacher=teacher, teacher_sha=sha,
                provenance=provenance, config=config, parameters=parameters,
                graph=graph, answer_ids=answer_ids)
            trainer._record(run_dir, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "generation": 1,
                "grade": "A",
                "optimizer_step": base.optimizer_step,
                "retained_optimizer_updates": 1,
                "recovered_at_student_sha256": base.sha256,
                "checkpoint_status": "RECORDED_AT_BOUNDARY",
            })
            _persist(run_dir, historical)
            before = json.loads(json.dumps(historical))
            with self.assertRaisesRegex(
                    ValueError, "SCHOOL.STATE.HISTORICAL_NOT_RESUMABLE"):
                _resume(
                    run_dir, manifest, course, sha,
                    grade_a_course=course, source_root=ROOT)
            self.assertEqual(read_generation(run_dir, 1), before)
            self.assertEqual(read_current(run_dir), before)
