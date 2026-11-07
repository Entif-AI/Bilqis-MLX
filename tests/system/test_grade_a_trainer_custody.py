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

class GradeATrainerCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    def test_failed_bundle_write_never_enters_active_bundles(self):
        def fail_after_partial_stage(directory, *args, **kwargs):
            directory.mkdir(parents=True)
            (directory / "manifest.json").write_text("partial stage")
            raise OSError("injected disk interruption")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch('bilqis_mlx.runtime.mlx_checkpoint.save_new_bundle',
                       side_effect=fail_after_partial_stage):
                with self.assertRaisesRegex(OSError, "injected disk interruption"):
                    _bundle_pointer(root, "interrupted-unique", {}, None, {},
                                    reserve_gib=0.)
            self.assertFalse((root / "bundles").exists())
            self.assertTrue((root / ".bundle-staging/interrupted-unique/manifest.json").is_file())
            self.assertEqual(_clean_staged_bundles(root),
                             {"discarded": ("interrupted-unique",), "quarantined": ()})
            self.assertFalse((root / ".bundle-staging").exists())
            # Failure after binary materialization retains it for an explicit
            # human recovery decision, outside active candidate retirement.
            staged = root / ".bundle-staging/completed-weights"
            staged.mkdir(parents=True)
            (staged / "model-and-own-adamw.safetensors").write_bytes(b"toy-weights")
            (staged / "manifest.json").write_text("partial")
            self.assertEqual(_clean_staged_bundles(root),
                             {"discarded": (), "quarantined": ("completed-weights",)})
            self.assertEqual((root / ".bundle-quarantine/completed-weights/"
                              "model-and-own-adamw.safetensors").read_bytes(),
                             b"toy-weights")

    def test_uncommitted_published_newer_student_is_saved_from_retirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            late = root / "bundles/candidate-after-crash"
            late.mkdir(parents=True)
            details = {"source_digest": AUDITED_PARENT.sha256,
                       "optimizer_step": 101, "safetensors_sha256": "f" * 64}
            with patch('bilqis_mlx.runtime.mlx_checkpoint.load_semantically_bound_bundle',
                       return_value=({}, None, details, {})):
                found = _quarantine_newer_uncommitted_bundles(root, set(), 100)
            self.assertEqual(found, ("candidate-after-crash",))
            self.assertFalse(late.exists())
            self.assertTrue((root / ".bundle-quarantine/candidate-after-crash").is_dir())
            event = json.loads((root / "events.jsonl").read_text().splitlines()[-1])
            self.assertEqual(event["optimizer_step"], 101)
            self.assertEqual(event["prior_committed_optimizer_step"], 100)

    def test_finder_metadata_cannot_block_bundle_custody_or_hide_unknown_files(self):
        from bilqis_mlx.learning.capability_frontier import retirement_plan, historical_frontier
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundles = root / "bundles"
            bundles.mkdir()
            finder = bundles / ".DS_Store"
            finder.write_bytes(b"Finder bookkeeping, not a student")
            self.assertEqual(retirement_plan(root, set()), ())
            self.assertEqual(historical_frontier(root), {})
            self.assertEqual(_quarantine_newer_uncommitted_bundles(root, set(), 20), ())
            self.assertFalse(finder.exists())
            unknown = bundles / "unexplained.bin"
            unknown.write_bytes(b"never silently ignore unknown files")
            with self.assertRaisesRegex(ValueError, "UNCOMMITTED_BUNDLE_UNSAFE_PATH"):
                _quarantine_newer_uncommitted_bundles(root, set(), 20)
            with self.assertRaisesRegex(ValueError, "CUSTODY_UNRECOGNIZED_BUNDLE"):
                retirement_plan(root, set())
            unknown.unlink()
            finder.symlink_to("/tmp/non-existent-unsafe-target")
            with self.assertRaisesRegex(ValueError, "UNCOMMITTED_BUNDLE_UNSAFE_PATH"):
                _quarantine_newer_uncommitted_bundles(root, set(), 20)
            self.assertTrue(finder.is_symlink())

    def test_snapshots_are_immutable_generations_with_one_latest_pointer(self):
        course = accepted_grade_a(self.manifest)
        student = Checkpoint("e"*64, "bundles/fixture", 116760, True)
        state = start_new(course, student)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = {"schema":"synthetic", "generation":1,
                     "school":self._serial(state)}
            _persist(root, first)
            normalized = json.loads(json.dumps(first))
            self.assertEqual(read_current(root),normalized)
            second = {**first, "generation":2}
            _persist(root, second)
            self.assertEqual(read_current(root),
                             json.loads(json.dumps(second)))
            self.assertEqual(read_generation(root, 1),
                             normalized)
            self.assertEqual(_state_from_json(second["school"], course),state)
            self.assertEqual(_persist(root, second), json.loads(json.dumps(second)))
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_GENERATION_COLLISION"):
                _persist(root, {**second, "model_bundle": "bundles/incorrect"})
            with operator_lock(root):
                with self.assertRaisesRegex(ValueError, "ANOTHER_OPERATOR_ACTIVE"):
                    with operator_lock(root):
                        pass

    @staticmethod
    def _serial(state):
        from dataclasses import asdict
        return asdict(state)

    @unittest.skipUnless(SOURCE.is_file(), "Original teacher/archive unavailable")
    def test_inherited_teacher_retains_original_policy_observations(self):
        manifest, old_course, engine, sha, teacher, provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
        course = live_course(old_course)
        # Prove the active path draws from constructors, even if the legacy
        # manifest's preserved fixed inventories are unavailable to it.
        manifest = {**manifest, "training_rows": [], "examination_rows": []}
        self.assertEqual(manifest["exam_count"], 72)
        self.assertEqual(provenance["teacher_origin_events"], teacher["events"])
        self.assertGreater(teacher["events"], 4000)
        self.assertGreater(len(teacher["strategies"]), 300)
        self.assertEqual(provenance["teacher_origin_step"], 116952)
        copy = deepcopy(teacher)
        import random
        key, policy = engine.pick(copy, "A", random.Random(52))
        self.assertEqual(set(policy), {"old","preview","depth","contrast","lr","distill"})
        engine.observe(copy, "A", key, .125)
        self.assertEqual(copy["events"], teacher["events"]+1)
        self.assertEqual(teacher["events"], provenance["teacher_origin_events"])
        self.assertIn("A", copy["grade_stats"])

    def test_synthetic_micro_transformer_training_step_updates_own_adamw(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
        mx.set_default_device(mx.cpu)
        rng = np.random.default_rng(18)
        d = 12
        shapes = {
            "embedding.weight": (32,d),
            "position.weight": (8,d),
            "norm.weight": (d,),
            "blocks.0.n1.weight": (d,),
            "blocks.0.n2.weight": (d,),
            "blocks.0.qkv.weight": (3*d,d),
            "blocks.0.proj.weight": (d,d),
            "blocks.0.up.weight": (2*d,d),
            "blocks.0.down.weight": (d,2*d),
        }
        params = {
            name: mx.array(rng.normal(0, .05, size=shape).astype(np.float32)
                           if len(shape) > 1 else np.ones(shape,dtype=np.float32))
            for name, shape in shapes.items()}
        opt = optim.AdamW(learning_rate=.00013, bias_correction=True)
        rows = [
            {"gold":"TRUE","tokens":[1,2,3,6]},
            {"gold":"FALSE","tokens":[4,5,6,7]},
        ]
        before = np.asarray(params["embedding.weight"]).copy()
        loss, norm = _train_step(mx, params, opt, rows,
                                 {"heads":3,"layers":1}, [6,7])
        self.assertTrue(math.isfinite(loss))
        self.assertTrue(math.isfinite(norm))
        self.assertEqual(int(opt.state["step"].item()), 1)
        self.assertFalse(np.array_equal(before,np.asarray(params["embedding.weight"])))
        self.assertEqual(len(opt.state)-2, len(shapes))
        for name in shapes:
            self.assertEqual(set(opt.state[name]), {"m","v"})
