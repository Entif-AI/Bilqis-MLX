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
from bilqis_mlx.boolean_composite import build_course as build_composite
from bilqis_mlx.boolean_identification import (
    answer_heads as idboolops_answer_heads,
    build_course as build_idboolops,
    draw_identification,
)
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.live_grade_c import answer_heads as numeric_answer_heads
from bilqis_mlx.live_grade_c import registry_graph as numeric_registry_graph
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.factory.live_releases import initial_course
from bilqis_mlx.factory.live_releases import boolean_successor
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.compatibility.schedule_program import (
    schedule_program_from_legacy_course,
)
from bilqis_mlx.factory.schedule import (
    ScheduleCapability, ScheduleGrade, ScheduleProgram,
)
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.learning.champion_confidence import perfect_role_roster
from bilqis_mlx.learning.epoch_championships import active_frontier
from bilqis_mlx.learning.grade_soup import grade_soup_recipe
from bilqis_mlx.learning.championship_witnesses import battery_from_exam, verified_battery


def _fake_executable_release(course):
    return SimpleNamespace(execution_plan=SimpleNamespace(
        capability_map=course.capability_map))


def _cohort_pointer(cohort, program):
    capabilities = tuple(dict.fromkeys(
        row["capability"] for row in cohort.rows))
    grade = next(
        grade for grade in reversed(program.grades)
        if any(cap.id in set(capabilities) for cap in grade.capabilities))
    return {
        "factory_release_sha256": "f" * 64,
        "capabilities": capabilities,
        "rubric_sha256": grade.assessment_sha256,
        "source_sha256": "c" * 64,
        "cohort_sha256": cohort.digest,
        "cohort_file": "cohorts/" + cohort.digest + ".json",
        "cohort_seed": cohort.seed,
    }


def _synthetic_program(grades):
    return ScheduleProgram(
        program_digest="d" * 64,
        grades=tuple(ScheduleGrade(
            grade,
            tuple(ScheduleCapability(capability, 2)
                  for capability in capabilities),
            (),
            "e" * 64,
        ) for grade, capabilities in grades),
        program_complete=False,
    )


class ChampionshipExamTests(TestCase):
    def test_c_era_config_rebuilds_only_idboolops_heads_for_prefix_incumbent(self):
        root = Path(__file__).resolve().parents[2]
        source = root / "vendor/legacy-v16"
        _, _, prefix_graph, _, _ = read_sources(source)
        grown_graph = numeric_registry_graph()
        current_heads = numeric_answer_heads(grown_graph, 3)
        current_heads["boolean_operator"] = idboolops_answer_heads(grown_graph)[
            "boolean_operator"]
        current = {
            "heads": 3,
            "layers": 1,
            "answer_heads": current_heads,
        }

        compatible = trainer._compatible_answer_config(current, prefix_graph)
        rebuilt = compatible["answer_heads"]
        self.assertNotIn("numeric_active", rebuilt)
        self.assertEqual(rebuilt["boolean_operator"],
                         idboolops_answer_heads(prefix_graph)["boolean_operator"])
        self.assertEqual(len(rebuilt["semantic_token"]["values"]),
                         len(prefix_graph["tokens"]))
        self.assertTrue(all(
            token_id < len(prefix_graph["tokens"])
            for head in rebuilt.values() for token_id in head["token_ids"]))

    def test_idboolops_panel_is_readable_by_compatible_historical_graph(self):
        root = Path(__file__).resolve().parents[2]
        source = root / "vendor/legacy-v16"
        manifest = json.loads((
            root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        a = initial_course(accepted_grade_a(manifest))
        b = boolean_successor(a, source)
        course = build_idboolops(build_composite(b, source), source)
        _, _, graph, _, _ = read_sources(source)
        rows = draw_identification(source, graph, seed=113)
        cohort = make_cohort(
            rows, generator_version=course.grades[-1].capabilities[-1].lesson_generator,
            seed=113, rubric_version=course.grades[-1].assessment_sha256)
        receipt = {
            "answer_ids": [6, 7],
            "config": {"answer_heads": idboolops_answer_heads(graph)},
        }
        readable = trainer._readable_championship_rows(cohort, graph, receipt)
        self.assertEqual(readable, cohort.rows)
        self.assertEqual({row["answer_kind"] for row in readable}, {"boolean_operator"})
        self.assertEqual({row["capability"] for row in readable}, {"B.IDBOOLOPS"})

    def test_idboolops_live_exam_factor_guard_checks_declared_domain_not_provider_balance(self):
        root = Path(__file__).resolve().parents[2]
        source = root / "vendor/legacy-v16"
        manifest = json.loads((
            root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        course = build_idboolops(
            build_composite(boolean_successor(
                initial_course(accepted_grade_a(manifest)), source), source), source)
        _, _, graph, _, _ = read_sources(source)
        rows = draw_identification(source, graph, seed=117)
        cohort = make_cohort(
            rows, generator_version=course.grades[-1].capabilities[-1].lesson_generator,
            seed=117, rubric_version=course.grades[-1].assessment_sha256)
        idboolops = course.grades[-1].capabilities[-1]
        family = idboolops.answer_families[0]
        self.assertEqual(family.kind, "boolean_operator")
        self.assertEqual({row["gold"] for row in cohort.rows}, set(family.values))
        self.assertEqual(
            {value: sum(row["gold"] == value for row in cohort.rows)
             for value in family.values},
            {value: 2 for value in family.values})
        release = _fake_executable_release(course)
        self.assertTrue(trainer._live_exam_factors_complete(
            release, cohort, {"B.IDBOOLOPS": 12}))

        broken_rows = list(cohort.rows)
        broken_rows[-1] = {**broken_rows[-1], "gold": "XNOR"}
        broken = make_cohort(
            broken_rows, generator_version=cohort.generator_version,
            seed=cohort.seed, rubric_version=cohort.rubric_version)
        self.assertFalse(trainer._live_exam_factors_complete(
            release, broken, {"B.IDBOOLOPS": 12}))

    def test_assessment_scope_hash_tracks_actual_scored_capabilities(self):
        full = ("A.IDENTITY", "A.LINK", "B.AND", "B.IFF")
        partial = {"A.IDENTITY": {}, "A.LINK": {}, "B.AND": {}}
        complete = {cap: {} for cap in full}
        self.assertEqual(
            trainer._assessment_scope_sha256(full, partial),
            trainer._fingerprint(("A.IDENTITY", "A.LINK", "B.AND")))
        self.assertEqual(
            trainer._assessment_scope_sha256(full, complete),
            trainer._fingerprint(full))
        self.assertNotEqual(
            trainer._assessment_scope_sha256(full, partial),
            trainer._assessment_scope_sha256(full, complete))

    def test_quarantine_b_and_does_not_suppress_complete_a_identity_title(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        course_a = initial_course(accepted_grade_a(manifest))
        course = boolean_successor(course_a, root / "vendor/legacy-v16")
        student = Checkpoint("a" * 64, "bundles/disposable", 10, True)
        school = replace(
            start_new(course, student), grade_index=1, stage="ASSESS_MAIN", queue=(),
            champions={"A": student})
        rubric, release, generator, _ = trainer._cohort_contract(course)
        cohort_rubric = course.grades[-1].assessment_sha256
        caps = tuple(cap.id for grade in course.grades for cap in grade.capabilities)
        blocked = "B.AND"
        identity_cap = "A.IDENTITY"

        def cohort(seed):
            return make_cohort([
                {"id": f"{seed}:{cap}:{i}", "capability": cap,
                 "gold": "TRUE" if i % 2 else "FALSE", "tokens": [1, 2]}
                for cap in caps for i in range(12)],
                generator_version=generator, seed=seed,
                rubric_version=cohort_rubric)

        candidate, routine = cohort(11), cohort(12)
        program = schedule_program_from_legacy_course(course)
        executable_release = _fake_executable_release(course)
        routine_active = make_cohort(
            [row for row in routine.rows if row["capability"] != blocked],
            generator_version=routine.generator_version, seed=routine.seed,
            rubric_version=routine.rubric_version)

        def predict(_mx, _parameters, rows, *_):
            return {row["id"]: row["gold"] for row in rows}

        graph = {"tokens": ["PAD"]}
        parameter_shapes = {"embedding.weight": [1, 1]}
        release_sha = "f" * 64
        identity = trainer.build_school_identity(
            course_sha256=course.digest(), semantic_graph_sha256=trainer._fingerprint(graph),
            parameter_shapes=parameter_shapes, factory_release_sha256=release_sha)
        receipt = {
            "school": asdict(school), "generation": 1, "run_id": "inert-quarantine",
            "curriculum_mode": release, "source_manifest_sha256": manifest["manifest_sha256"],
            "config": {}, "answer_ids": [6, 7], "teacher_misses": [],
            "semantic_graph_sha256": trainer._fingerprint(graph),
            "parameter_shapes": parameter_shapes, "factory_release_sha256": release_sha,
            "championship_school_identity": identity,
                   "championship_checkpoint_origins": {student.sha256: "A"},
                   "last_retained_update_grade": "A",
        }
        with TemporaryDirectory() as temp, ExitStack() as stack:
            patches = {
                "_read_executable_factory_release_artifact":
                    lambda *_: executable_release,
                "schedule_program_from_executable_release":
                    lambda *_: program,
                "_routine_executable_cohort":
                    lambda *_a, **_k: (
                        routine_active, _cohort_pointer(routine_active, program)),
                "_candidate_executable_cohort":
                    lambda *_a, **_k: (
                        routine_active, _cohort_pointer(routine_active, program)),
                "quarantined_capabilities": lambda *_: (blocked,),
                "_predictions": predict,
                "_commit_scored_student": lambda *_a, **_k: (school, {}, (), []),
                "_score_parent_for_paired_s3": lambda *_: (None, "INERT_FIXTURE"),
                "summarize_completed_exam_safely": lambda *_: {"findings": [], "active_warnings": []},
                "apply_paired_checkpoint_s3": lambda warning, **_: warning,
                "advance_peaks": lambda *_a, **_k: ([], {}),
                "_cook_new_grade_soups": lambda *_a, **_k: ({}, ()),
                "_advance": lambda _run, saved, advanced, **extra: {
                    **saved, "school": asdict(advanced), "last_exam": extra["last_exam"]},
                "_with_delivery_outbox": lambda saved, *_: saved,
                "_boundary_delivery_events": lambda *_: [],
                "_persist": lambda _run, saved: saved,
                "_publish_boundary": lambda *_a, **_k: None,
            }
            for name, function in patches.items():
                stack.enter_context(patch.object(trainer, name, side_effect=function))
            stack.enter_context(patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256=cohort_rubric)))
            completed = trainer._take_exam(
                None, Path(temp), receipt, manifest, course, root, root,
                {"embedding.weight": SimpleNamespace(shape=(1, 1))},
                SimpleNamespace(state={}), graph, reserve_gib=0)
        self.assertIn(identity_cap, completed["mentor_epoch"]["active_roles"])
        self.assertNotIn(blocked, completed["mentor_epoch"]["active_roles"])
        b_roles = [role for cap, role in completed["mentor_epoch"]["active_roles"].items()
                   if cap.startswith("B.") and cap != blocked]
        self.assertTrue(b_roles)
        protected = {item["sha256"] for item in trainer._mentor_epoch_references(completed)}
        self.assertTrue(all(role["checkpoint"]["sha256"] in protected
                            for role in b_roles))
        self.assertIn(blocked, completed["last_exam"]["withheld_capabilities"])

    def test_quarantining_entire_later_grade_keeps_cumulative_grade_rubric(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        course_a = initial_course(accepted_grade_a(manifest))
        course = boolean_successor(course_a, root / "vendor/legacy-v16")
        student = Checkpoint("a" * 64, "bundles/disposable", 10, True)
        school = replace(
            start_new(course, student), grade_index=1, stage="ASSESS_MAIN", queue=(),
            champions={"A": student})
        rubric, release, generator, _ = trainer._cohort_contract(course)
        caps = tuple(cap.id for grade in course.grades for cap in grade.capabilities)
        blocked = tuple(cap.id for cap in course.grades[-1].capabilities)

        def cohort(seed):
            return make_cohort([
                {"id": f"{seed}:{cap}:{i}", "capability": cap,
                 "gold": "TRUE" if i % 2 else "FALSE", "tokens": [1, 2]}
                for cap in caps for i in range(12)],
                generator_version=generator, seed=seed, rubric_version=release)

        candidate, routine = cohort(31), cohort(32)

        def filtered(*args):
            source = args[-2]
            selected = make_cohort(
                [row for row in source.rows if row["capability"] not in set(blocked)],
                generator_version=source.generator_version, seed=source.seed,
                rubric_version=rubric)
            return selected, "unused"

        def predict(_mx, _parameters, rows, *_):
            return {row["id"]: row["gold"] for row in rows}

        graph = {"tokens": ["PAD"]}
        parameter_shapes = {"embedding.weight": [1, 1]}
        release_sha = "f" * 64
        identity = trainer.build_school_identity(
            course_sha256=course.digest(), semantic_graph_sha256=trainer._fingerprint(graph),
            parameter_shapes=parameter_shapes, factory_release_sha256=release_sha)
        receipt = {
            "school": asdict(school), "generation": 1,
            "run_id": "inert-whole-grade-quarantine",
            "curriculum_mode": release,
            "source_manifest_sha256": manifest["manifest_sha256"],
            "config": {}, "answer_ids": [6, 7], "teacher_misses": [],
            "semantic_graph_sha256": trainer._fingerprint(graph),
            "parameter_shapes": parameter_shapes,
            "factory_release_sha256": release_sha,
            "championship_school_identity": identity,
            "championship_checkpoint_origins": {student.sha256: "A"},
            "last_retained_update_grade": "A",
        }
        with TemporaryDirectory() as temp, ExitStack() as stack:
            for source_cohort in (candidate, routine):
                trainer._persist_live_cohort(Path(temp), manifest, course, source_cohort)
            program = schedule_program_from_legacy_course(course)
            executable_release = _fake_executable_release(course)
            selected = filtered(None, None, None, routine, None)[0]
            patches = {
                "_read_executable_factory_release_artifact": lambda *_: executable_release,
                "schedule_program_from_executable_release": lambda *_: program,
                "_routine_executable_cohort": lambda *_a, **_k: (selected, {**_cohort_pointer(selected, program), "rubric_sha256": rubric}),
                "_candidate_executable_cohort": lambda *_a, **_k: (selected, _cohort_pointer(selected, program)),
                "quarantined_capabilities": lambda *_: blocked,
                "_predictions": predict,
                "_commit_scored_student": lambda *_a, **_k: (school, {}, (), []),
                "_score_parent_for_paired_s3": lambda *_: (None, "INERT_FIXTURE"),
                "summarize_completed_exam_safely": lambda *_: {"findings": [], "active_warnings": []},
                "apply_paired_checkpoint_s3": lambda warning, **_: warning,
                "advance_peaks": lambda *_a, **_k: ([], {}),
                "_cook_new_grade_soups": lambda *_a, **_k: ({}, ()),
                "_advance": lambda _run, saved, advanced, **extra: {
                    **saved, "school": asdict(advanced), "last_exam": extra["last_exam"]},
                "_with_delivery_outbox": lambda saved, *_: saved,
                "_boundary_delivery_events": lambda *_: [],
                "_persist": lambda _run, saved: saved,
                "_publish_boundary": lambda *_a, **_k: None,
            }
            for name, function in patches.items():
                stack.enter_context(patch.object(trainer, name, side_effect=function))
            stack.enter_context(patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256=rubric)))
            completed = trainer._take_exam(
                None, Path(temp), receipt, manifest, course, root, root,
                {"embedding.weight": SimpleNamespace(shape=(1, 1))},
                SimpleNamespace(state={}), graph, reserve_gib=0)

        self.assertEqual(completed["last_exam"]["exam_rubric_sha256"], rubric)
        self.assertEqual(set(completed["last_exam"]["withheld_capabilities"]), set(blocked))

    def test_newly_quarantined_after_measurement_is_not_retroactively_unmeasured(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        course_a = initial_course(accepted_grade_a(manifest))
        course = boolean_successor(course_a, root / "vendor/legacy-v16")
        student = Checkpoint("a" * 64, "bundles/disposable", 10, True)
        school = replace(
            start_new(course, student), grade_index=1, stage="ASSESS_MAIN", queue=(),
            champions={"A": student})
        rubric, release, generator, _ = trainer._cohort_contract(course)
        cohort_rubric = course.grades[-1].assessment_sha256
        caps = tuple(cap.id for grade in course.grades for cap in grade.capabilities)
        blocked_after = "A.LINK"

        def cohort(seed):
            return make_cohort([
                {"id": f"{seed}:{cap}:{i}", "capability": cap,
                 "gold": "TRUE" if i % 2 else "FALSE", "tokens": [1, 2]}
                for cap in caps for i in range(12)],
                generator_version=generator, seed=seed,
                rubric_version=cohort_rubric)

        candidate, routine = cohort(21), cohort(22)
        program = schedule_program_from_legacy_course(course)
        executable_release = _fake_executable_release(course)

        def predict(_mx, _parameters, rows, *_):
            return {row["id"]: row["gold"] for row in rows}

        def advance_after(**kwargs):
            return (kwargs["stagnation"], [], kwargs["routine_advanced"],
                    (blocked_after,))

        graph = {"tokens": ["PAD"]}
        parameter_shapes = {"embedding.weight": [1, 1]}
        release_sha = "f" * 64
        identity = trainer.build_school_identity(
            course_sha256=course.digest(), semantic_graph_sha256=trainer._fingerprint(graph),
            parameter_shapes=parameter_shapes, factory_release_sha256=release_sha)
        receipt = {
            "school": asdict(school), "generation": 1, "run_id": "inert-blocked-after",
            "curriculum_mode": release, "source_manifest_sha256": manifest["manifest_sha256"],
            "config": {}, "answer_ids": [6, 7], "teacher_misses": [],
            "semantic_graph_sha256": trainer._fingerprint(graph),
            "parameter_shapes": parameter_shapes, "factory_release_sha256": release_sha,
            "championship_school_identity": identity,
            "championship_checkpoint_origins": {student.sha256: "A"},
            "last_retained_update_grade": "A",
        }
        with TemporaryDirectory() as temp, ExitStack() as stack:
            patches = {
                "_read_executable_factory_release_artifact":
                    lambda *_: executable_release,
                "schedule_program_from_executable_release":
                    lambda *_: program,
                "_routine_executable_cohort":
                    lambda *_a, **_k: (
                        routine, _cohort_pointer(routine, program)),
                "_candidate_executable_cohort":
                    lambda *_a, **_k: (
                        candidate, _cohort_pointer(candidate, program)),
                "quarantined_capabilities": lambda *_: (),
                "_advance_stagnation_after_routine": advance_after,
                "_promotion_due_after_routine": lambda *_: False,
                "_predictions": predict,
                "_commit_scored_student": lambda *_a, **_k: (school, {}, (), []),
                "_score_parent_for_paired_s3": lambda *_: (None, "INERT_FIXTURE"),
                "summarize_completed_exam_safely": lambda *_: {"findings": [], "active_warnings": []},
                "apply_paired_checkpoint_s3": lambda warning, **_: warning,
                "advance_peaks": lambda *_a, **_k: ([], {}),
                "_cook_new_grade_soups": lambda *_a, **_k: ({}, ()),
                "_advance": lambda _run, saved, advanced, **extra: {
                    **saved, "school": asdict(advanced), "last_exam": extra["last_exam"]},
                "_with_delivery_outbox": lambda saved, *_: saved,
                "_boundary_delivery_events": lambda *_: [],
                "_persist": lambda _run, saved: saved,
                "_publish_boundary": lambda *_a, **_k: None,
            }
            for name, function in patches.items():
                stack.enter_context(patch.object(trainer, name, side_effect=function))
            stack.enter_context(patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256=cohort_rubric)))
            completed = trainer._take_exam(
                None, Path(temp), receipt, manifest, course, root, root,
                {"embedding.weight": SimpleNamespace(shape=(1, 1))},
                SimpleNamespace(state={}), graph, reserve_gib=0)

        self.assertIn(blocked_after, completed["mentor_epoch"]["active_roles"])
        self.assertNotIn(blocked_after, completed["last_exam"]["withheld_capabilities"])
        self.assertIn(blocked_after, completed["last_exam"]["stagnation_quarantined"])

    def test_older_incumbent_competes_on_complete_readable_grade_without_claiming_school_score(self):
        old = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1], "row_contract_sha256": {}}
        graph = {"tokens": ["PAD", "TRUE", "NEW"], "nodes": [0, 1, 2], "row_contract_sha256": {}}
        pointer = {"filename": "bundles/old", "sha256": "a" * 64,
                   "optimizer_step": 10, "model_and_native_adamw": True}
        current = Checkpoint("b" * 64, "bundles/current", 20, True)
        course = SimpleNamespace(grades=[
            SimpleNamespace(id=g, assessment_sha256="d" * 64,
                            capabilities=[SimpleNamespace(id=c)])
            for g, c in (("A", "A.X"), ("C", "C.NEW"))])
        cohort = make_cohort([
            {"id": f"{cap}:{i}", "capability": cap, "gold": "TRUE", "tokens": [token]}
            for cap, token in (("A.X", 1), ("C.NEW", 2)) for i in range(2)],
            generator_version="fixture", seed=7, rubric_version="fixture")
        receipt = {"config": {}, "answer_ids": [1], "source_manifest_sha256": "c" * 64,
                   "championship_school_identity": {"sha256": "f" * 64},
                   "championship_checkpoint_origins": {"b" * 64: "A"},
                   "mentor_epoch": {"introduced_grade": "C", "source_graph_sha256": trainer._fingerprint(graph),
                                    "championship_school_identity": {"sha256": "f" * 64},
                                    "active_roles": {"A.X": {"capability": "A.X", "correct": 1, "total": 2,
                                                               "origin_grade": "A",
                                                               "checkpoint": pointer}}}}
        scores = {cap: {"correct": 2, "total": 2} for cap in ("A.X", "C.NEW")}
        program = _synthetic_program(
            (("A", ("A.X",)), ("C", ("C.NEW",))))
        with (
            TemporaryDirectory() as temp,
            patch.object(trainer, "assessment_capabilities", return_value=tuple(scores)),
            patch.object(
                trainer, "_read_executable_factory_release_artifact",
                return_value=SimpleNamespace()),
            patch.object(
                trainer, "schedule_program_from_executable_release",
                return_value=program),
            patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256="d" * 64)),
            patch.object(trainer, "load_semantically_bound_bundle", return_value=(
                {}, None, {"safetensors_sha256": "a" * 64, "optimizer_step": 10}, old)),
            patch.object(trainer, "_predictions", side_effect=lambda _m, _w, rows, *_: {
                row["id"]: row["gold"] for row in rows}) as inference,
        ):
            _, _, incumbents = trainer._epoch_paired_examinations(
                None, Path(temp), receipt, course,
                SimpleNamespace(current_student=current, grade="A"),
                cohort, scores, {r["id"]: r["gold"] for r in cohort.rows}, graph)
        self.assertEqual(set(incumbents["a" * 64]["scores"]), {"A.X"})
        self.assertEqual({r["capability"] for r in inference.call_args.args[2]}, {"A.X"})

    def test_title_grade_selects_incumbent_panel_independent_of_checkpoint_origin(self):
        old = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1], "row_contract_sha256": {}}
        graph = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1], "row_contract_sha256": {}}
        incumbent = {"filename": "bundles/old", "sha256": "a" * 64,
                     "optimizer_step": 10, "model_and_native_adamw": True}
        current = Checkpoint("b" * 64, "bundles/current", 20, True)
        course = SimpleNamespace(grades=[
            SimpleNamespace(id="A", assessment_sha256="d" * 64,
                            capabilities=[SimpleNamespace(id="A.X")]),
            SimpleNamespace(id="B", assessment_sha256="d" * 64,
                            capabilities=[SimpleNamespace(id="B.X")]),
        ])
        cohort = make_cohort([
            {"id": f"{cap}:{i}", "capability": cap, "gold": "TRUE", "tokens": [1]}
            for cap in ("A.X", "B.X") for i in range(2)],
            generator_version="fixture", seed=8, rubric_version="fixture")
        receipt = {
            "config": {}, "answer_ids": [1], "source_manifest_sha256": "c" * 64,
            "championship_school_identity": {"sha256": "f" * 64},
            "championship_checkpoint_origins": {"b" * 64: "A"},
            "mentor_epoch": {
                "introduced_grade": "B",
                "source_graph_sha256": trainer._fingerprint(graph),
                "championship_school_identity": {"sha256": "f" * 64},
                "active_roles": {
                    "B.X": {"capability": "B.X", "correct": 1, "total": 2,
                            "origin_grade": "B", "checkpoint": incumbent},
                },
            },
        }
        scores = {cap: {"correct": 2, "total": 2} for cap in ("A.X", "B.X")}
        program = _synthetic_program(
            (("A", ("A.X",)), ("B", ("B.X",))))
        with (
            TemporaryDirectory() as temp,
            patch.object(trainer, "assessment_capabilities", return_value=tuple(scores)),
            patch.object(
                trainer, "_read_executable_factory_release_artifact",
                return_value=SimpleNamespace()),
            patch.object(
                trainer, "schedule_program_from_executable_release",
                return_value=program),
            patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256="d" * 64)),
            patch.object(trainer, "load_semantically_bound_bundle", return_value=(
                {}, None, {"safetensors_sha256": "a" * 64, "optimizer_step": 10}, old)),
            patch.object(trainer, "_predictions", side_effect=lambda _m, _w, rows, *_: {
                row["id"]: row["gold"] for row in rows}) as inference,
        ):
            _, challenger, incumbents = trainer._epoch_paired_examinations(
                None, Path(temp), receipt, course,
                SimpleNamespace(current_student=current, grade="A"),
                cohort, scores, {r["id"]: r["gold"] for r in cohort.rows}, graph,
                challenge_grade="B")
        self.assertEqual(challenger["challenge_grade"], "B")
        self.assertEqual(challenger["checkpoint_origin_grade"], "A")
        self.assertEqual(set(incumbents["a" * 64]["scores"]), {"B.X"})
        self.assertEqual({r["capability"] for r in inference.call_args.args[2]}, {"B.X"})

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
            role = hydrated["active_roles"]["A.X"]
            battery = verified_battery(role)
            self.assertEqual({q["id"] for segment in battery for q in segment["questions"]},
                             {"x0", "x1"})
            with patch.object(trainer, "_predictions", side_effect=[
                    {"x0": "TRUE", "x1": "FALSE"},
                    {"x0": "WRONG", "x1": "FALSE"}]) as infer:
                first = trainer._fresh_battery_results(None, root, receipt, role, {}, old)
                second = trainer._fresh_battery_results(None, root, receipt, role, {}, old)
            self.assertEqual(infer.call_count, 2)
            self.assertNotEqual(first, second)

    def test_fresh_battery_batches_verified_segments_into_one_model_inference(self):
        graph = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1],
                 "row_contract_sha256": {}}
        receipt = {"source_manifest_sha256": "c" * 64,
                   "config": {}, "answer_ids": [1]}
        contexts = []
        cohorts = []
        for seed, prefix in ((1, "x"), (2, "y")):
            rows = [
                {"id": prefix + "0", "capability": "A.X",
                 "gold": "TRUE", "tokens": [1]},
                {"id": prefix + "1", "capability": "A.X",
                 "gold": "FALSE", "tokens": [1]},
            ]
            cohort = make_cohort(
                rows, generator_version="fixture", seed=seed,
                rubric_version="fixture")
            context = {
                "cohort_sha256": cohort.digest,
                "rubric_sha256": "d" * 64,
                "cohort_rubric_sha256": "d" * 64,
                "assessment_scope_sha256": "e" * 64,
                "source_graph_sha256": trainer._fingerprint(graph),
                "source_oracle_sha256": "c" * 64,
                "scores": {"A.X": {"correct": 2, "total": 2}},
                "questions": {"A.X": [
                    {"id": row["id"], "gold": row["gold"]} for row in rows]},
                "correct_questions": {"A.X": [
                    {"id": row["id"], "gold": row["gold"]} for row in rows]},
            }
            contexts.append(context)
            cohorts.append((cohort, rows))
        role = {
            "capability": "A.X",
            "surviving_battery": list(
                battery_from_exam(contexts[0], ("A.X",)) +
                battery_from_exam(contexts[1], ("A.X",))),
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cohorts").mkdir()
            for cohort, rows in cohorts:
                (root / "cohorts" / (cohort.digest + ".json")).write_text(
                    json.dumps({
                        "cohort_sha256": cohort.digest,
                        "rubric_sha256": "d" * 64,
                        "source_manifest_sha256": "c" * 64,
                        "schema": "fixture",
                        "generator_version": "fixture",
                        "seed": cohort.seed,
                        "rows": rows,
                    }))
            answers = {"x0": "TRUE", "x1": "FALSE",
                       "y0": "TRUE", "y1": "FALSE"}
            with patch.object(trainer, "_predictions", return_value=answers) as infer:
                result = trainer._fresh_battery_results(
                    None, root, receipt, role, {}, graph)

        self.assertEqual(infer.call_count, 1)
        self.assertEqual(len(infer.call_args.args[2]), 4)
        self.assertEqual(set(result), {
            segment["sha256"] for segment in role["surviving_battery"]})
        self.assertTrue(all(len(correct) == 2 for correct in result.values()))

    def test_title_match_reinfers_both_models_for_current_panel_and_battery(self):
        graph = {"tokens": ["PAD", "TRUE"], "nodes": [0, 1],
                 "row_contract_sha256": {}}
        rows = [{"id": "x0", "capability": "A.X", "gold": "TRUE", "tokens": [1]},
                {"id": "x1", "capability": "A.X", "gold": "FALSE", "tokens": [1]}]
        cohort = make_cohort(rows, generator_version="fixture", seed=1,
                             rubric_version="d" * 64)
        incumbent = {"filename": "bundles/old", "sha256": "a" * 64,
                     "optimizer_step": 10, "model_and_native_adamw": True}
        challenger_pointer = {"filename": "bundles/new", "sha256": "b" * 64,
                              "optimizer_step": 11, "model_and_native_adamw": True}
        context = {
            "cohort_sha256": cohort.digest, "rubric_sha256": "d" * 64,
            "cohort_rubric_sha256": "d" * 64,
            "assessment_scope_sha256": "e" * 64,
            "source_graph_sha256": trainer._fingerprint(graph),
            "source_oracle_sha256": "c" * 64,
        }
        earning = {
            **context, "checkpoint": incumbent,
            "scores": {"A.X": {"correct": 2, "total": 2}},
            "questions": {"A.X": [{"id": r["id"], "gold": r["gold"]} for r in rows]},
            "correct_questions": {
                "A.X": [{"id": r["id"], "gold": r["gold"]} for r in rows]},
        }
        role = {
            "capability": "A.X", "checkpoint": incumbent,
            "surviving_battery": list(battery_from_exam(earning, ("A.X",))),
        }
        epoch = {"active_roles": {"A.X": role}}
        challenger = {
            **context, "checkpoint": challenger_pointer,
            "scores": {"A.X": {"correct": 2, "total": 2}},
            "questions": earning["questions"],
            "correct_questions": earning["correct_questions"],
        }
        receipt = {"source_manifest_sha256": "c" * 64,
                   "config": {}, "answer_ids": [1]}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cohorts").mkdir()
            (root / "cohorts" / (cohort.digest + ".json")).write_text(json.dumps({
                "cohort_sha256": cohort.digest, "rubric_sha256": "d" * 64,
                "source_manifest_sha256": "c" * 64, "schema": "d" * 64,
                "generator_version": "fixture", "seed": 1, "rows": rows}))
            predictions = [
                {"x0": "TRUE", "x1": "FALSE"},   # incumbent fresh current
                {"x0": "WRONG", "x1": "FALSE"},  # contender fresh current
                {"x0": "WRONG", "x1": "FALSE"},  # incumbent fresh battery
                {"x0": "TRUE", "x1": "FALSE"},   # contender fresh battery
            ]
            with (patch.object(trainer, "load_semantically_bound_bundle", return_value=(
                    {}, None, {"safetensors_sha256": "a" * 64,
                               "optimizer_step": 10}, graph)),
                  patch.object(trainer, "_predictions", side_effect=predictions) as infer):
                match = trainer._fresh_title_match(
                    None, root, receipt, epoch, cohort, challenger, {}, graph, "A.X")
        self.assertEqual(infer.call_count, 4)
        self.assertEqual(match["incumbent_current_exam"]["scores"]["A.X"]["correct"], 2)
        self.assertEqual(match["challenger_current_exam"]["scores"]["A.X"]["correct"], 1)
        segment = role["surviving_battery"][0]["sha256"]
        self.assertEqual(len(match["battery_results"]["a" * 64][segment]), 1)
        self.assertEqual(len(match["battery_results"]["b" * 64][segment]), 2)

    def test_fresh_nonflash_exam_earns_roles_and_max_votes_without_graduation(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        course = initial_course(accepted_grade_a(manifest))
        student = Checkpoint("a" * 64, "bundles/disposable", 10, True)
        school = replace(start_new(course, student), stage="ASSESS_MAIN", queue=())
        rubric, release, generator, _ = trainer._cohort_contract(course)
        cohort_rubric = course.grades[-1].assessment_sha256
        caps = tuple(cap.id for cap in course.grades[0].capabilities)

        def cohort(seed):
            return make_cohort([
                {"id": f"{seed}:{cap}:{i}", "capability": cap,
                 "gold": "TRUE" if i % 2 else "FALSE", "tokens": [1, 2]}
                for cap in caps for i in range(12)],
                generator_version=generator, seed=seed,
                rubric_version=cohort_rubric)

        candidate, routine = cohort(1), cohort(2)
        program = schedule_program_from_legacy_course(course)
        executable_release = _fake_executable_release(course)

        def predict(_mx, _parameters, rows, *_):
            return {r["id"]: r["gold"] if (
                int(r["id"].split(":")[-1]) < 8 or
                (r["id"].startswith("2:") and r["capability"] == caps[0]))
                else "WRONG" for r in rows}

        def soups(_mx, _run, _receipt, frontier, _course, _graph, **_kwargs):
            recipe = grade_soup_recipe(frontier, "A", caps)
            return {"A": recipe}, ("A",)

        graph = {"tokens": ["PAD"]}
        parameter_shapes = {"embedding.weight": [1, 1]}
        release_sha = "f" * 64
        championship_identity = trainer.build_school_identity(
            course_sha256=course.digest(),
            semantic_graph_sha256=trainer._fingerprint(graph),
            parameter_shapes=parameter_shapes,
            factory_release_sha256=release_sha)
        receipt = {"school": asdict(school), "generation": 1, "run_id": "inert",
                   "curriculum_mode": release, "source_manifest_sha256": manifest["manifest_sha256"],
                   "config": {}, "answer_ids": [6, 7], "teacher_misses": [],
                   "semantic_graph_sha256": trainer._fingerprint(graph),
                   "parameter_shapes": parameter_shapes,
                   "factory_release_sha256": release_sha,
                   "championship_school_identity": championship_identity,
                   "championship_checkpoint_origins": {},
                   "last_retained_update_grade": "A"}
        with TemporaryDirectory() as temp, ExitStack() as stack:
            patches = {
                "_read_executable_factory_release_artifact":
                    lambda *_: executable_release,
                "schedule_program_from_executable_release":
                    lambda *_: program,
                "_routine_executable_cohort":
                    lambda *_a, **_k: (
                        routine, _cohort_pointer(routine, program)),
                "_candidate_executable_cohort":
                    lambda *_a, **_k: (
                        candidate, _cohort_pointer(candidate, program)),
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
            stack.enter_context(patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(
                    rubric_sha256=cohort_rubric)))
            completed = trainer._take_exam(
                None, Path(temp), receipt, manifest, course, root, root,
                {"embedding.weight": SimpleNamespace(shape=(1, 1))},
                SimpleNamespace(state={}), graph, reserve_gib=0)
        self.assertEqual(completed["last_exam"]["exam_plane"], "ROUTINE")
        self.assertEqual(set(completed["mentor_epoch"]["active_roles"]), set(caps))
        self.assertEqual(completed["school"]["champions"], {})
        epoch = completed["mentor_epoch"]
        votes = perfect_role_roster(active_frontier(epoch), epoch["active_grade_soups"])
        self.assertEqual(votes[0]["capabilities"], (caps[0],))
        self.assertIn(caps[0], completed["last_exam"]["championship_roles"])
