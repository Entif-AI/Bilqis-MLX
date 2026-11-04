from bilqis_mlx.runtime.tests._executable_assessment_fixtures import *  # noqa: F403

class ExecutableAssessmentTests(BaseExecutableAssessmentTests):
    def test_generalization_is_fresh_from_promotion_and_burned_prior_attempt(self):
        receipt = self.receipt()
        scope = (*self.a_scope, "B.AND", "B.IFF")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, promotion_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=11)
            first, first_pointer = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=11,
                promotion_pointer=promotion_pointer)
            self.assertNotEqual(first.digest, promotion.digest)
            self.assertFalse(
                {row["id"] for row in first.rows} &
                {row["id"] for row in promotion.rows})

            receipt["burned_generalization_cohorts_v2"] = [first_pointer]
            receipt["generation"] += 1
            second, second_pointer = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=11,
                promotion_pointer=promotion_pointer)
            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual(second_pointer, first_pointer)
            self.assertNotEqual(
                {row["id"] for row in second.rows},
                {row["id"] for row in first.rows})

    def test_generalization_collision_does_not_permanently_exclude_its_rows(self):
        """A burned instrument forbids the set, not its unexposed specimens."""
        receipt = self.receipt()
        receipt["burned_generalization_cohorts_v2"] = [{"fixture": "burned"}]
        scope = ("B.AND",)
        first, contract = self.draw(self.reduced, scope, seed=101)
        alternate, _ = self.draw(self.reduced, scope, seed=102)
        first_rows = list(first.rows)
        first_stratum = (
            first_rows[0]["capability"], first_rows[0].get("answer_kind", "binary"),
            first_rows[0]["gold"], tuple(first_rows[0].get("operand_truths", ())),
            first_rows[0].get("universe_size"))
        first_ids = {item["id"] for item in first_rows}
        replacement = next(
            row for row in alternate.rows
            if row["id"] not in first_ids
            and (
                row["capability"], row.get("answer_kind", "binary"), row["gold"],
                tuple(row.get("operand_truths", ())), row.get("universe_size"))
            == first_stratum)
        second = make_cohort(
            [replacement, *first_rows[1:]],
            generator_version=contract.generator_version, seed=alternate.seed,
            rubric_version=contract.rubric_sha256)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, promotion_pointer = _promotion_executable_cohort(
                root, self.receipt(), self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=17)
            self.assertFalse(
                {row["id"] for row in promotion.rows}
                & {row["id"] for row in first.rows})
            draws = 0

            def controlled_draw(*args, **kwargs):
                nonlocal draws
                draws += 1
                return (first if draws == 1 else second), contract

            burned_set = frozenset(row["id"] for row in first.rows)
            with patch(
                    "bilqis_mlx.runtime._assessment.executable_lifecycle._draw_executable_scope_cohort",
                    side_effect=controlled_draw), patch(
                    "bilqis_mlx.runtime._assessment.executable_lifecycle._burned_generalization_evidence",
                    return_value=({first.digest}, {burned_set})):
                fresh, _ = _generalization_executable_cohort(
                    root, receipt, self.manifest, self.reduced, self.registry,
                    None, self.graph, capabilities=scope, assessment_epoch=17,
                    promotion_pointer=promotion_pointer)

            self.assertNotEqual(
                frozenset(row["id"] for row in fresh.rows), burned_set)
            self.assertIn(replacement["id"], {row["id"] for row in fresh.rows})

    def test_generalization_preserves_burned_cohort_from_prior_larger_scope(self):
        # A later grade's active scope may shrink after assessment scheduling.
        # Previously burned source evidence remains valid under its own signed
        # scope, not the newly scheduled assessment's narrower scope.
        receipt = self.receipt()
        current_scope = self.a_scope
        historical_scope = tuple(
            item.capability_id for item in self.reduced.execution_plan.capabilities)
        self.assertNotEqual(current_scope, historical_scope)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            historical, contract = self.draw(self.reduced, historical_scope, seed=72)
            burned_pointer = _persist_executable_cohort(
                root, self.manifest, contract, historical)
            promotion, promotion_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=12)
            receipt["burned_generalization_cohorts_v2"] = [burned_pointer]
            fresh, _ = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=12,
                promotion_pointer=promotion_pointer)
            self.assertNotEqual(fresh.digest, promotion.digest)
            self.assertNotEqual(fresh.digest, historical.digest)

    def test_burned_cohort_remains_readable_after_release_change(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _persist_executable_factory_release(root, self.full)
            historical, contract = self.draw(self.full, self.a_scope, seed=72)
            burned_pointer = _persist_executable_cohort(root, self.manifest, contract, historical)
            _, promotion_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=self.a_scope, assessment_epoch=12)
            receipt['burned_generalization_cohorts_v2'] = [burned_pointer]
            fresh, pointer = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=self.a_scope, assessment_epoch=12,
                promotion_pointer=promotion_pointer)
            self.assertNotEqual(fresh.digest, historical.digest)
            self.assertEqual(pointer['factory_release_sha256'], self.reduced.release_sha256)
            self.assertEqual(receipt['burned_generalization_cohorts_v2'], [burned_pointer])

    def test_generalization_verifies_burned_cohort_under_its_historical_release(self):
        receipt = self.receipt()
        current_scope = tuple(
            item.capability_id for item in self.reduced.execution_plan.capabilities)
        historical_scope = tuple(
            item.capability_id for item in self.full.execution_plan.capabilities)
        self.assertTrue(set(historical_scope) - set(current_scope))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _persist_executable_factory_release(root, self.full)
            _persist_executable_factory_release(root, self.reduced)
            historical, contract = self.draw(self.full, historical_scope, seed=73)
            burned_pointer = _persist_executable_cohort(
                root, self.manifest, contract, historical)
            promotion, promotion_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=13)
            receipt["burned_generalization_cohorts_v2"] = [burned_pointer]
            fresh, _ = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=13,
                promotion_pointer=promotion_pointer)
            self.assertNotEqual(fresh.digest, promotion.digest)
            self.assertNotEqual(fresh.digest, historical.digest)
