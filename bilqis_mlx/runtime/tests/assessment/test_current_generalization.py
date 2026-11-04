from bilqis_mlx.runtime.tests._assessment_fixtures import *  # noqa: F403

class AssessmentTests(BaseGradeAssessmentTests):
    def test_failed_generalization_cohort_is_burned_for_next_qualification(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, first_pointer = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            self.assertNotEqual(first.digest, promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            receipt["generation"] += 1
            second, second_pointer = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=pointer["cohort_sha256"])
            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual(second_pointer["cohort_sha256"], first_pointer["cohort_sha256"])

    def test_burned_generalization_does_not_permanently_embargo_untrained_rows(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            receipt["generation"] += 1

            replacement = deepcopy(first.rows[0])
            replacement["id"] = "f" * 64
            replacement["source_id"] = replacement["id"]
            overlapping = (replacement, *deepcopy(first.rows[1:]))

            with patch(
                    "bilqis_mlx.runtime.assessment._draw_live_rows",
                    return_value=overlapping):
                second, _ = _generalization_cohort(
                    root, receipt, self.manifest, self.course, SOURCE, self.graph,
                    promotion_sha256=promotion.digest)

            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual({row["id"] for row in second.rows},
                                {row["id"] for row in first.rows})
            self.assertGreater(
                len({row["id"] for row in second.rows} &
                    {row["id"] for row in first.rows}),
                0,
            )

    def test_burned_generalization_cannot_repeat_same_specimen_set_under_new_seed(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            receipt["generation"] += 1

            with patch(
                    "bilqis_mlx.runtime._assessment.current_lifecycle._draw_live_rows",
                    return_value=deepcopy(first.rows)):
                with self.assertRaisesRegex(
                        ValueError, "FRESH_GENERALIZATION_COHORT_EXHAUSTED"):
                    _generalization_cohort(
                        root, receipt, self.manifest, self.course, SOURCE, self.graph,
                        promotion_sha256=promotion.digest)

    def test_teacher_exposed_generalization_miss_stays_out_of_later_cohort(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            taught = deepcopy(first.rows[0])
            receipt["teacher_misses"] = [taught]
            receipt["generation"] += 1

            replacement = deepcopy(taught)
            replacement["id"] = "e" * 64
            replacement["source_id"] = replacement["id"]
            candidate = (replacement, *deepcopy(first.rows[1:]))

            with patch(
                    "bilqis_mlx.runtime.assessment._draw_live_rows",
                    return_value=candidate):
                second, _ = _generalization_cohort(
                    root, receipt, self.manifest, self.course, SOURCE, self.graph,
                    promotion_sha256=promotion.digest)

            self.assertNotIn(taught["id"], {row["id"] for row in second.rows})

    def test_generalization_does_not_repeat_promotion_specimen_identities(self):
        receipt = self.receipt()
        receipt["run_id"] = "review-repro"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            fresh, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            self.assertFalse({row["id"] for row in promotion.rows} &
                             {row["id"] for row in fresh.rows})
            self.assertEqual(len(fresh.rows), 72)
            for cap in self.course.capability_map:
                self.assertEqual(sum(row["capability"] == cap and row["gold"] == "TRUE"
                                     for row in fresh.rows), 6)

    def test_exam_constructions_remain_eligible_for_teaching(self):
        with tempfile.TemporaryDirectory() as temp:
            cohort, _ = self.draw(Path(temp), self.receipt())
            rows = list(cohort.rows)
            batch = choose_lesson_batch(rows, {"depth": 1, "contrast": 1.0}, 18, batch_size=8)
            self.assertEqual(len(batch), 8)
            self.assertTrue({r["id"] for r in batch} <= {r["id"] for r in rows})

    def test_changed_question_content_is_rejected_without_replacing_exam(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            path = root / pointer["cohort_file"]
            payload = json.loads(path.read_text())
            payload["rows"][0]["gold"] = "FALSE" if payload["rows"][0]["gold"] == "TRUE" else "TRUE"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "COHORT_.*DRIFT"):
                self.draw(root, receipt)
