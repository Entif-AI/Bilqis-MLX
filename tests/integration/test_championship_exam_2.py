"""Focused championship exam behavior."""
from tests.integration.championship_exam_support import *  # noqa: F403,F405

class ChampionshipExamTests(TestCase):  # noqa: F405
    def _quarantine_fixture(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        course_a = initial_course(accepted_grade_a(manifest))
        course = boolean_successor(course_a, root / "vendor/legacy-v16")
        student = Checkpoint("a" * 64, "bundles/disposable", 10, True)
        school = replace(start_new(course, student), grade_index=1, stage="ASSESS_MAIN",
                         queue=(), champions={"A": student})
        _, release, generator, _ = trainer._cohort_contract(course)
        cohort_rubric = course.grades[-1].assessment_sha256
        caps = tuple(cap.id for grade in course.grades for cap in grade.capabilities)
        blocked = "B.AND"
        routine = make_cohort([
            {"id": f"12:{cap}:{i}", "capability": cap,
             "gold": "TRUE" if i % 2 else "FALSE", "tokens": [1, 2]}
            for cap in caps for i in range(12)],
            generator_version=generator, seed=12, rubric_version=cohort_rubric)
        program = schedule_program_from_legacy_course(course)
        routine_active = make_cohort(
            [row for row in routine.rows if row["capability"] != blocked],
            generator_version=routine.generator_version, seed=routine.seed,
            rubric_version=routine.rubric_version)
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
        return root, manifest, course, school, program, routine_active, graph, receipt, cohort_rubric, blocked

    def _run_quarantine_exam(self, fixture):
        root, manifest, course, school, program, routine_active, graph, receipt, rubric, blocked = fixture
        patches = {
            "_read_executable_factory_release_artifact": lambda *_: _fake_executable_release(course),
            "schedule_program_from_executable_release": lambda *_: program,
            "_routine_executable_cohort": lambda *_a, **_k: (
                routine_active, _cohort_pointer(routine_active, program)),
            "_candidate_executable_cohort": lambda *_a, **_k: (
                routine_active, _cohort_pointer(routine_active, program)),
            "quarantined_capabilities": lambda *_: (blocked,),
            "_predictions": _perfect_predictions,
            "_commit_scored_student": lambda *_a, **_k: (school, {}, (), []),
            "_score_parent_for_paired_s3": lambda *_: (None, "INERT_FIXTURE"),
            "summarize_completed_exam_safely": lambda *_: {"findings": [], "active_warnings": []},
            "apply_paired_checkpoint_s3": lambda warning, **_: warning,
            "advance_peaks": lambda *_a, **_k: ([], {}),
            "_cook_new_grade_soups": lambda *_a, **_k: ({}, ()),
            "_advance": lambda _run, saved, advanced, **extra: {
                **saved, "school": asdict(advanced), "last_exam": extra["last_exam"]},
            "_with_delivery_outbox": lambda saved, *_: saved,
            "_boundary_delivery_events": lambda *_: [], "_persist": lambda _run, saved: saved,
            "_publish_boundary": lambda *_a, **_k: None,
        }
        with TemporaryDirectory() as temp, ExitStack() as stack:
            for name, function in patches.items():
                stack.enter_context(_patch_owner(name, side_effect=function))
            stack.enter_context(patch(
                "bilqis_mlx.factory.assessment.assessment_scope_contract",
                return_value=SimpleNamespace(rubric_sha256=rubric)))
            return trainer._take_exam(
                None, Path(temp), receipt, manifest, course, root, root,
                {"embedding.weight": SimpleNamespace(shape=(1, 1))},
                SimpleNamespace(state={}), graph, reserve_gib=0)

    def test_quarantine_b_and_does_not_suppress_complete_a_identity_title(self):
        fixture = self._quarantine_fixture()
        completed = self._run_quarantine_exam(fixture)
        blocked = fixture[-1]
        identity_cap = "A.IDENTITY"
        self.assertIn(identity_cap, completed["mentor_epoch"]["active_roles"])
        self.assertNotIn(blocked, completed["mentor_epoch"]["active_roles"])
        b_roles = [role for cap, role in completed["mentor_epoch"]["active_roles"].items()
                   if cap.startswith("B.") and cap != blocked]
        self.assertTrue(b_roles)
        protected = {item["sha256"] for item in trainer._mentor_epoch_references(completed)}
        self.assertTrue(all(role["checkpoint"]["sha256"] in protected for role in b_roles))
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
        candidate = _synthetic_exam_cohort(
            caps, seed=31, generator_version=generator, rubric_version=release)
        routine = _synthetic_exam_cohort(
            caps, seed=32, generator_version=generator, rubric_version=release)

        def filtered(*args):
            source = args[-2]
            selected = make_cohort(
                [row for row in source.rows if row["capability"] not in set(blocked)],
                generator_version=source.generator_version, seed=source.seed,
                rubric_version=rubric)
            return selected, "unused"

        graph = {"tokens": ["PAD"]}
        parameter_shapes = {"embedding.weight": [1, 1]}
        release_sha = "f" * 64
        receipt = _exam_receipt(
            school=school, run_id="inert-whole-grade-quarantine",
            release=release, manifest=manifest, course=course, graph=graph,
            parameter_shapes=parameter_shapes, release_sha=release_sha,
            championship_origins={student.sha256: "A"})
        with TemporaryDirectory() as temp:
            for source_cohort in (candidate, routine):
                trainer._persist_live_cohort(Path(temp), manifest, course, source_cohort)
            program = schedule_program_from_legacy_course(course)
            executable_release = _fake_executable_release(course)
            selected = filtered(None, None, None, routine, None)[0]
            patches = _exam_patches(
                executable_release=executable_release, program=program,
                routine=selected, candidate=selected, school=school,
                predict=_perfect_predictions,
                extra={
                    "_routine_executable_cohort": lambda *_a, **_k: (
                        selected, {**_cohort_pointer(selected, program),
                                   "rubric_sha256": rubric}),
                    "quarantined_capabilities": lambda *_: blocked,
                })
            completed = _take_inert_exam(
                temp=temp, receipt=receipt, manifest=manifest, course=course,
                root=root, graph=graph, patches=patches, rubric_sha256=rubric)

        self.assertEqual(completed["last_exam"]["exam_rubric_sha256"], rubric)
        self.assertEqual(set(completed["last_exam"]["withheld_capabilities"]), set(blocked))
