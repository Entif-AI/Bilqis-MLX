"""Focused championship exam behavior."""
from tests.integration.championship_exam_support import *  # noqa: F403,F405

class ChampionshipExamTests(TestCase):  # noqa: F405
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
        candidate = _synthetic_exam_cohort(
            caps, seed=21, generator_version=generator,
            rubric_version=cohort_rubric)
        routine = _synthetic_exam_cohort(
            caps, seed=22, generator_version=generator,
            rubric_version=cohort_rubric)
        program = schedule_program_from_legacy_course(course)
        executable_release = _fake_executable_release(course)

        def advance_after(**kwargs):
            return (kwargs["stagnation"], [], kwargs["routine_advanced"],
                    (blocked_after,))

        graph = {"tokens": ["PAD"]}
        parameter_shapes = {"embedding.weight": [1, 1]}
        release_sha = "f" * 64
        receipt = _exam_receipt(
            school=school, run_id="inert-blocked-after", release=release,
            manifest=manifest, course=course, graph=graph,
            parameter_shapes=parameter_shapes, release_sha=release_sha,
            championship_origins={student.sha256: "A"})
        patches = _exam_patches(
            executable_release=executable_release, program=program,
            routine=routine, candidate=candidate, school=school,
            predict=_perfect_predictions,
            extra={
                "quarantined_capabilities": lambda *_: (),
                "_advance_stagnation_after_routine": advance_after,
                "_promotion_due_after_routine": lambda *_a, **_k: False,
            })
        with TemporaryDirectory() as temp:
            completed = _take_inert_exam(
                temp=temp, receipt=receipt, manifest=manifest, course=course,
                root=root, graph=graph, patches=patches,
                rubric_sha256=cohort_rubric)

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
            patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities', return_value=tuple(scores)),
            patch('bilqis_mlx.runtime.admission._read_executable_factory_release_artifact',
                return_value=SimpleNamespace()),
            patch('bilqis_mlx.factory.schedule.schedule_program_from_executable_release',
                return_value=program),
            patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256="d" * 64)),
            patch('bilqis_mlx.runtime.mlx_checkpoint.load_semantically_bound_bundle', return_value=(
                {}, None, {"safetensors_sha256": "a" * 64, "optimizer_step": 10}, old)),
            patch('bilqis_mlx.learning.student_ops._predictions', side_effect=lambda _m, _w, rows, *_: {
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
            patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities', return_value=tuple(scores)),
            patch('bilqis_mlx.runtime.admission._read_executable_factory_release_artifact',
                return_value=SimpleNamespace()),
            patch('bilqis_mlx.factory.schedule.schedule_program_from_executable_release',
                return_value=program),
            patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256="d" * 64)),
            patch('bilqis_mlx.runtime.mlx_checkpoint.load_semantically_bound_bundle', return_value=(
                {}, None, {"safetensors_sha256": "a" * 64, "optimizer_step": 10}, old)),
            patch('bilqis_mlx.learning.student_ops._predictions', side_effect=lambda _m, _w, rows, *_: {
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
