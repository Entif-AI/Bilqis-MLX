from bilqis_mlx.runtime.tests._assessment_fixtures import *  # noqa: F403

class AssessmentTests(BaseGradeAssessmentTests):
    def test_routine_grade_evaluation_redraws_after_each_boundary(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            receipt["generation"] += 30
            receipt = json.loads(json.dumps(receipt))
            redraw, saved = self.draw(root, receipt)
            self.assertNotEqual(redraw.digest, original.digest)
            self.assertNotEqual(redraw.seed, original.seed)
            self.assertNotEqual(saved["cohort_sha256"], pointer["cohort_sha256"])

    def test_championship_cohort_keeps_source_rubric_distinct_from_assessment_rubric(self):
        rows = ({"id": "q0", "capability": "A.IDENTITY", "gold": "TRUE"},)
        cohort = make_cohort(
            rows, generator_version="source-v1", seed=17,
            rubric_version="admitted-a-b-release")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "cohorts"
            path.mkdir()
            (path / f"{cohort.digest}.json").write_text(json.dumps({
                "schema": "admitted-a-b-release",
                "source_manifest_sha256": "d" * 64,
                "rubric_sha256": "c" * 64,
                "generator_version": "source-v1",
                "seed": 17,
                "cohort_sha256": cohort.digest,
                "rows": list(rows),
            }))
            loaded = load_championship_cohort(root, {
                "cohort_sha256": cohort.digest,
                "rubric_sha256": "b" * 64,
                "cohort_rubric_sha256": "c" * 64,
                "source_oracle_sha256": "d" * 64,
            })
        self.assertEqual(loaded.digest, cohort.digest)

    def test_candidate_and_routine_cohorts_both_rotate_independently(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            routine, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            first = _candidate_cohort(root, receipt, self.manifest,
                                      self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, routine.digest)
            receipt["generation"] += 1
            second = _candidate_cohort(root, receipt, self.manifest,
                                       self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, second.digest)
            redrawn, redrawn_pointer = self.draw(root, receipt)
            self.assertNotEqual(redrawn.digest, routine.digest)
            self.assertNotEqual(redrawn_pointer["cohort_sha256"], pointer["cohort_sha256"])

    def test_promotion_attempt_is_distinct_and_failed_attempt_remains_fixed(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            routine, _ = self.draw(root, receipt)
            first, first_pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, routine.digest)
            again, again_pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertEqual(again.digest, first.digest)
            self.assertEqual(again_pointer, first_pointer)
            receipt["qualification_cohort"] = first_pointer
            receipt["generation"] += 1
            second, second_pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertEqual(second.digest, first.digest)
            self.assertEqual(second_pointer, first_pointer)

    def test_promotion_return_after_another_enrollment_uses_a_new_attempt(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            receipt["qualification_cohort"] = pointer
            receipt["school"]["grade_exam_epoch"] += 1
            receipt["generation"] += 1
            second, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, second.digest)

    def test_returning_to_the_same_grade_gets_new_questions(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            receipt["school"]["grade_exam_epoch"] += 1
            receipt["generation"] += 1
            revisited, _ = self.draw(root, receipt)
            self.assertNotEqual(revisited.digest, original.digest)
            self.assertNotEqual(revisited.seed, original.seed)

    def test_legacy_failed_exam_does_not_freeze_a_new_routine_boundary(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cohort, pointer = self.draw(root, receipt)
            receipt["school"].pop("grade_exam_epoch")
            receipt["last_exam"] = {key: pointer[key] for key in (
                "cohort_sha256", "cohort_seed", "cohort_file")}
            receipt["last_exam"].update(
                exam_rubric_sha256=self.course.grades[0].assessment_sha256,
                scores={c.id: {"correct": 0, "total": 12}
                        for c in self.course.grades[0].capabilities})
            receipt["generation"] += 1
            redrawn, _ = self.draw(root, receipt)
            self.assertNotEqual(redrawn.digest, cohort.digest)
