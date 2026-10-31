"""Factory training compilation through the released adapter boundary."""

from bilqis_mlx.runtime.tests.test_atlas_training_adapter import (
    AtlasTrainingAdapterTest, BamfTarget, BilqisError, CurriculumProfile,
    Literal, SourceAdapterRegistry, SourceExecutionContext, _source_context,
    answer_plan_for, closed_source_fixture, compile_executable_factory_release, compile_prefix,
    compile_training_batch, describe_delivered_teaching, feature_requests_for, features_for,
    from_legacy_course, replace, source_ast_for,
)


class TrainingCompilationTests(AtlasTrainingAdapterTest):
    def test_real_factory_rows_and_delivery_bind_typed_source_and_target(self):
        item = self.compile(self.rows).rows[0]
        self.assertEqual(item.model_input.prefix.ast, Literal('1,2', 'TokenSequence'))
        self.assertEqual(item.model_input.features, (('1,2', 'subject', 'fixture.schema', 'public'),))
        self.assertEqual(item.target.value, 'FALSE')
        self.assertEqual(item.target.token_id, 1)
        self.assertEqual(len(item.model_input.eligibility_digest), 64)
        self.assertNotEqual(item.model_input.eligibility_digest, 'e' * 64)
        self.assertIn(('modalityID', 'answer.binary/v1'), item.model_input.answer_plan)
        self.assertEqual(item.provenance.row_id, self.rows[0]['id'])
        self.assertEqual(item.provenance.source_id, 'source-1')
        self.assertEqual(item.provenance.requested_count, 3)
        self.assertEqual(item.provenance.delivered_count, 1)
        self.assertEqual(item.provenance.optimizer_step_seed, 42)
        self.assertEqual(item.provenance.teacher_strategy, (('policy', 'focused'),))

    def test_unreleased_or_forged_delivery_is_rejected(self):
        for mutation in ({'capability': 'NOT.ADMITTED'}, {'gold': 'UNKNOWN'}, {'answer_kind': 'unsupported'}):
            with self.subTest(mutation=mutation), self.assertRaises((BilqisError, KeyError)):
                self.compile([{**self.rows[0], **mutation}])
        with self.assertRaises(BilqisError):
            self.compile(self.rows, release_sha='f' * 64)

    def test_registered_modality_receives_structured_source_targets_and_plan(self):
        row = {**self.rows[0], 'gold': {'decisions': ['FALSE', 'END_FRAME']},
               'answer_plan': {'decisions': [{'id': 'value', 'depends_on': []},
                                             {'id': 'end', 'depends_on': ['value']}]},
               'auxiliary_labels': {'role': 'subject'}}
        def encode(evidence, head):
            self.assertEqual(evidence.gold, (('decisions', ('FALSE', 'END_FRAME')),))
            self.assertEqual(evidence.auxiliary_labels, (('role', 'subject'),))
            self.assertIn(('modalityID', 'answer.binary/v1'), evidence.answer_plan)
            self.assertIn(('maximum_decisions', 2), evidence.answer_plan)
            return BamfTarget('binary', evidence.gold, (head.token_ids[0], None), (True, False))
        item = self.compile([row], encoders={'binary': encode}).rows[0]
        self.assertEqual(item.target.value, (('decisions', ('FALSE', 'END_FRAME')),))
        self.assertEqual(item.target.mask, (True, False))

    def test_direct_delivery_cannot_claim_another_capability(self):
        wrong = self.context.draw_rows(seed=19, capability='Z.C1', each=1)
        with self.assertRaises(BilqisError):
            self.compile(wrong)

    def test_native_output_is_bound_to_released_semantic_identity(self):
        row = {**self.rows[0], 'native_output': {'identity': 'cogal.value.false', 'token_id': 1}}
        item = self.compile([row]).rows[0]
        self.assertEqual(item.native_target.kind, 'semantic_token')
        self.assertEqual(item.native_target.value, 'cogal.value.false')
        self.assertEqual(item.native_target.token_id, 1)
        with self.assertRaises(BilqisError):
            self.compile([{**row, 'native_output': {'identity': 'cogal.value.true', 'token_id': 2}}])

    def test_grade_label_does_not_select_adapter_behavior(self):
        first = self.compile([{**self.rows[0], 'grade': 'A'}]).rows[0]
        second = self.compile([{**self.rows[0], 'grade': 'Z'}]).rows[0]
        self.assertEqual(first.model_input, second.model_input)
        self.assertEqual(first.target, second.target)
        self.assertEqual(first.provenance, second.provenance)

    def test_duplicate_delivered_row_identity_is_rejected(self):
        rows = [self.rows[0], dict(self.rows[0])]
        with self.assertRaises(BilqisError):
            self.compile(rows)

    def test_atomic_binary_operator_and_numeric_release_modalities(self):
        from bilqis_mlx.curriculum import AnswerFamily
        from bilqis_mlx.factory.answers import AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality, fixed_domain
        for kind, values, identities in (
            ('binary', ('FALSE', 'TRUE'), ('cogal.value.false', 'cogal.value.true')),
            ('boolean_operator', ('NOT', 'AND'), ('cogal.operator.NOT', 'cogal.operator.AND')),
            ('numeric_active', ('0', '1'), ('school.number.0', 'school.number.1'))):
            with self.subTest(kind=kind):
                course, _, sources, _, _ = closed_source_fixture()
                grade = course.grades[0]
                course = replace(course, grades=(replace(grade, capabilities=tuple(
                    replace(cap, answer_families=(AnswerFamily(kind, values),)) for cap in grade.capabilities)),))
                graph = {'tokens': ['fixture.padding', *identities]}
                base = sources.require('fixture.z-generator/v1', 'fixture.z-oracle/v1')
                def draw(**kwargs):
                    return tuple({**row, 'answer_kind': kind, 'gold': values[index % 2], 'tokens': [1, 2],
                        **({'native_output': {'identity': identities[index % 2], 'token_id': index % 2 + 1}}
                           if kind == 'numeric_active' else {})}
                        for index, row in enumerate(base.draw(**kwargs)))
                providers = SourceAdapterRegistry((replace(base, draw=draw, check=lambda row, **kw: row['gold'] in values),))
                answers = AnswerModalityRegistry((RegisteredAnswerModality(
                    AnswerModality(kind, 'fixture.answer/' + kind, 'a' * 64), fixed_domain(values),
                    lambda value: identities[values.index(value)]),))
                curriculum, bindings = from_legacy_course(course)
                release = compile_executable_factory_release(curriculum, bindings, CurriculumProfile.full(),
                    providers, answers, source_root=None, graph=graph, verification_seed=17)
                self.context = SourceExecutionContext(release, graph, None, providers, answers)
                rows = self.context.draw_rows(seed=17, capability='Z.C0', each=1)
                item = self.compile(rows).rows[0]
                self.assertEqual(item.target.kind, kind)
                self.assertEqual(item.target.value, values[0])
                self.assertEqual(item.model_input.prefix.ast, Literal('1,2', 'TokenSequence'))
                if kind == 'numeric_active':
                    self.assertEqual(item.native_target.value, 'school.number.0')

    def test_actual_release_grade_permutation_preserves_prepared_semantics(self):
        first = self.compile(self.rows)
        release = self.context.release
        curriculum = replace(release.curriculum, grades=tuple(replace(grade, grade_id='Q') for grade in release.curriculum.grades))
        changed = compile_executable_factory_release(curriculum, release.source_bindings, CurriculumProfile.full(),
            self.context.source_registry, self.context.answer_registry, source_root=None,
            graph=self.context.graph, verification_seed=17)
        self.context = SourceExecutionContext(changed, self.context.graph, None,
            self.context.source_registry, self.context.answer_registry)
        second = self.compile(self.rows)
        self.assertNotEqual(first.release_sha256, second.release_sha256)
        self.assertNotEqual(
            first.rows[0].model_input.eligibility_digest,
            second.rows[0].model_input.eligibility_digest)
        self.assertEqual(
            replace(first.rows[0].model_input,
                    eligibility_digest=second.rows[0].model_input.eligibility_digest),
            second.rows[0].model_input)
        self.assertEqual(first.rows[0].target, second.rows[0].target)
        self.assertEqual(first.rows[0].provenance, second.rows[0].provenance)

    def test_delivery_content_tampering_is_rejected(self):
        delivery = describe_delivered_teaching(self.context.release, 'Z.C0', 'source.direct/Z.C0', self.rows)
        changed = [{**self.rows[0], 'gold': 'TRUE'}]
        frames_for_ast, task, frontier, policy = _source_context(
            changed, self.context.release.release_sha256, {}, "allow")
        with self.assertRaises(BilqisError):
            compile_training_batch(changed, self.context, {}, delivery=delivery, delivery_capability='Z.C0',
                delivery_release_sha256=self.context.release.release_sha256,
                teacher_strategy={'policy': 'focused'}, requested_count=3, optimizer_step_seed=42,
                rehearsal_by_id={}, visible_ends={}, source_ast_for=source_ast_for,
                compile_prefix=compile_prefix, feature_requests_for=feature_requests_for, features_for=features_for, answer_plan_for=lambda *args: {**answer_plan_for(*args), 'generation_binding': self.model_generation},
            frames_for_ast=frames_for_ast, task_scope=task,
            source_frontier=frontier, eligibility_policy=policy,
            generation_binding=self.model_generation)
