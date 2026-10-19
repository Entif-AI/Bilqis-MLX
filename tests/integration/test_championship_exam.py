"""Normal exams mint advisory champions before whole-grade graduation."""
from contextlib import ExitStack
from dataclasses import asdict, replace
import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx import trainer
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.factory.live_releases import initial_course
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.learning.champion_confidence import perfect_role_roster
from bilqis_mlx.learning.epoch_championships import active_frontier
from bilqis_mlx.learning.grade_soup import grade_soup_recipe


class ChampionshipExamTests(TestCase):
    def test_older_incumbent_competes_on_complete_readable_grade_without_claiming_school_score(self):
        old = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1], "row_contract_sha256": {}}
        graph = {"tokens": ["PAD", "TRUE", "NEW"], "nodes": [0, 1, 2], "row_contract_sha256": {}}
        pointer = {"filename": "bundles/old", "sha256": "a" * 64,
                   "optimizer_step": 10, "model_and_native_adamw": True}
        current = Checkpoint("b" * 64, "bundles/current", 20, True)
        course = SimpleNamespace(grades=[
            SimpleNamespace(id=g, capabilities=[SimpleNamespace(id=c)])
            for g, c in (("A", "A.X"), ("C", "C.NEW"))])
        cohort = make_cohort([
            {"id": f"{cap}:{i}", "capability": cap, "gold": "TRUE", "tokens": [token]}
            for cap, token in (("A.X", 1), ("C.NEW", 2)) for i in range(2)],
            generator_version="fixture", seed=7, rubric_version="fixture")
        receipt = {"config": {}, "answer_ids": [1], "source_manifest_sha256": "c" * 64,
                   "mentor_epoch": {"introduced_grade": "C", "source_graph_sha256": trainer._fingerprint(graph),
                                    "active_roles": {"A.X": {"capability": "A.X", "correct": 1, "total": 2,
                                                               "checkpoint": pointer}}}}
        scores = {cap: {"correct": 2, "total": 2} for cap in ("A.X", "C.NEW")}
        with (
            TemporaryDirectory() as temp,
            patch.object(trainer, "assessment_capabilities", return_value=tuple(scores)),
            patch.object(trainer, "_cohort_contract", return_value=("d" * 64, "fixture", "fixture", "e" * 64)),
            patch.object(trainer, "load_semantically_bound_bundle", return_value=(
                {}, None, {"safetensors_sha256": "a" * 64, "optimizer_step": 10}, old)),
            patch.object(trainer, "_predictions", side_effect=lambda _m, _w, rows, *_: {
                row["id"]: row["gold"] for row in rows}) as inference,
        ):
            _, _, incumbents = trainer._epoch_paired_examinations(
                None, Path(temp), receipt, course, SimpleNamespace(current_student=current),
                cohort, scores, {r["id"]: r["gold"] for r in cohort.rows}, graph)
        self.assertEqual(set(incumbents["a" * 64]["scores"]), {"A.X"})
        self.assertEqual({r["capability"] for r in inference.call_args.args[2]}, {"A.X"})

    def test_legacy_earning_witness_preserves_compatible_historical_graph(self):
        old = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1],
               "row_contract_sha256": {"PAD": "p", "TRUE": "t"}}
        current = {"tokens": old["tokens"] + ["NEW"], "nodes": [0, 1, 2],
                   "row_contract_sha256": {**old["row_contract_sha256"], "NEW": "n"}}
        rows = [{"id": "x0", "capability": "A.X", "gold": "TRUE", "tokens": [1]},
                {"id": "x1", "capability": "A.X", "gold": "FALSE", "tokens": [1]}]
        cohort = make_cohort(rows, generator_version="fixture", seed=1, rubric_version="fixture")
        pointer = {"filename": "bundles/old", "sha256": "a" * 64,
                   "optimizer_step": 10, "model_and_native_adamw": True}
        role = {"capability": "A.X", "cohort_sha256": cohort.digest,
                "rubric": "b" * 64, "correct": 1, "total": 2, "checkpoint": pointer}
        epoch = {"active_roles": {"A.X": role}}
        receipt = {"source_manifest_sha256": "c" * 64, "config": {}, "answer_ids": [1]}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cohorts").mkdir()
            (root / "cohorts" / (cohort.digest + ".json")).write_text(json.dumps({
                "cohort_sha256": cohort.digest, "rubric_sha256": "b" * 64,
                "source_manifest_sha256": "c" * 64, "schema": "fixture",
                "generator_version": "fixture", "seed": 1, "rows": rows}))
            bundle = root / pointer["filename"]
            bundle.mkdir(parents=True)
            (bundle / "model-and-own-adamw.safetensors").write_bytes(b"inert fixture")
            with (patch.object(trainer, "_cached_frozen_champion", return_value=({}, old)),
                  patch.object(trainer, "_predictions", return_value={"x0": "TRUE", "x1": "WRONG"})):
                hydrated = trainer._hydrate_championship_witnesses(
                    None, root, receipt, epoch, current)
            proof = hydrated["active_roles"]["A.X"]["qualification_witnesses"][0]
            self.assertEqual(proof["source_graph_sha256"], trainer._fingerprint(old))
            self.assertEqual({q["id"] for q in proof["questions"]}, {"x0", "x1"})
            self.assertNotIn("qualification_witnesses", role)
            with patch.object(trainer, "_predictions", return_value={"x0": "TRUE", "x1": "FALSE"}) as infer:
                scores = trainer._championship_witness_scores(
                    None, root, receipt, [hydrated["active_roles"]["A.X"]] * 2, {}, {})
            self.assertEqual(set(scores[proof["sha256"]]), {"x0", "x1"})
            self.assertEqual(infer.call_count, 1)

    def test_fresh_nonflash_exam_earns_roles_and_max_votes_without_graduation(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        course = initial_course(accepted_grade_a(manifest))
        student = Checkpoint("a" * 64, "bundles/disposable", 10, True)
        school = replace(start_new(course, student), stage="ASSESS_MAIN", queue=())
        rubric, release, generator, _ = trainer._cohort_contract(course)
        caps = tuple(cap.id for cap in course.grades[0].capabilities)

        def cohort(seed):
            return make_cohort([
                {"id": f"{seed}:{cap}:{i}", "capability": cap,
                 "gold": "TRUE" if i % 2 else "FALSE", "tokens": [1, 2]}
                for cap in caps for i in range(12)],
                generator_version=generator, seed=seed, rubric_version=release)

        candidate, routine = cohort(1), cohort(2)

        def predict(_mx, _parameters, rows, *_):
            return {r["id"]: r["gold"] if (
                int(r["id"].split(":")[-1]) < 8 or
                (r["id"].startswith("2:") and r["capability"] == caps[0]))
                else "WRONG" for r in rows}

        def soups(_mx, _run, _receipt, frontier, _course, _graph, **_kwargs):
            recipe = grade_soup_recipe(frontier, "A", caps)
            return {"A": recipe}, ("A",)

        receipt = {"school": asdict(school), "generation": 1, "run_id": "inert",
                   "curriculum_mode": release, "source_manifest_sha256": manifest["manifest_sha256"],
                   "config": {}, "answer_ids": [6, 7], "teacher_misses": []}
        with TemporaryDirectory() as temp, ExitStack() as stack:
            for source_cohort in (candidate, routine):
                trainer._persist_live_cohort(Path(temp), manifest, course, source_cohort)
            patches = {
                "_grade_test_cohort": lambda *_: (routine, {}),
                "_candidate_cohort": lambda *_: candidate,
                "_introduced_cohort": lambda *a: (a[-1], "unused"),
                "_without_stagnant_capabilities": lambda *a: (a[-2], "unused"),
                "_predictions": predict,
                "_commit_scored_student": lambda *_a, **_k: (school, {}, (), []),
                "_score_parent_for_paired_s3": lambda *_: (None, "INERT_FIXTURE"),
                "summarize_completed_exam_safely": lambda *_: {"findings": [], "active_warnings": []},
                "apply_paired_checkpoint_s3": lambda warning, **_: warning,
                "advance_peaks": lambda *_a, **_k: ([], {}),
                "_cook_new_grade_soups": soups,
                "_advance": lambda _run, saved, advanced, **extra: {
                    **saved, "school": asdict(advanced), "last_exam": extra["last_exam"]},
                "_with_delivery_outbox": lambda saved, *_: saved,
                "_boundary_delivery_events": lambda *_: [],
                "_persist": lambda _run, saved: saved,
                "_publish_boundary": lambda *_a, **_k: None,
            }
            for name, function in patches.items():
                stack.enter_context(patch.object(trainer, name, side_effect=function))
            completed = trainer._take_exam(
                None, Path(temp), receipt, manifest, course, root, root,
                {}, SimpleNamespace(state={}), {"tokens": ["PAD"]}, reserve_gib=0)
        self.assertEqual(completed["last_exam"]["exam_plane"], "ROUTINE")
        self.assertEqual(set(completed["mentor_epoch"]["active_roles"]), set(caps))
        self.assertEqual(completed["school"]["champions"], {})
        epoch = completed["mentor_epoch"]
        votes = perfect_role_roster(active_frontier(epoch), epoch["active_grade_soups"])
        self.assertEqual(votes[0]["capabilities"], (caps[0],))
        self.assertIn(caps[0], completed["last_exam"]["championship_roles"])
