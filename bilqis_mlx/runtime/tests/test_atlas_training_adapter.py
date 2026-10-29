"""Provisional Factory-to-BAMF contract witnesses; no neural state is used."""
from dataclasses import dataclass, replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.factory.tests.test_teaching import closed_source_fixture
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.atlas_training_adapter import BamfTarget, compile_training_batch, require_current_release
from bilqis_mlx.semantics.foundation.core import Literal


@dataclass(frozen=True)
class EligibleFixture:
    frames: tuple
    digest: str
    allowed: bool


def frames_for_ast(ast):
    return (ast,)


def check_context_eligibility(frames, task_scope, source_frontier, policy):
    return EligibleFixture(frames, 'e' * 64, policy == 'allow')


def eligible_source_for(result):
    if not result.allowed:
        raise ValueError('context held')
    return result.frames[0], result.digest


@dataclass(frozen=True)
class CompiledPrefixFixture:
    ast: Literal
    visible_end: int


def source_ast_for(tokens):
    return Literal(','.join(str(token) for token in tokens), 'TokenSequence')


def compile_prefix(ast, visible_end, release, compiler_config):
    if not isinstance(ast, Literal):
        raise AssertionError('A05 requires a typed source AST')
    return CompiledPrefixFixture(ast, visible_end)


def feature_requests_for(prefix):
    return ((prefix.ast.value, 'subject', 'fixture.schema', 'public'),)


def answer_plan_for(prefix, release, capability, kind):
    head = next(head for head in release.answer_heads if head.kind == kind)
    return {'modalityID': head.modality_id, 'input_prefix_end': prefix.visible_end,
            'decisions': [{'id': 'value', 'roleID': 'answer', 'occurrence': 0,
                           'kind': 'VALUE', 'legalValues': list(head.values), 'depends_on': []},
                          {'id': 'end', 'roleID': 'end', 'occurrence': 0,
                           'kind': 'CONTROL', 'legalValues': ['END_FRAME'], 'depends_on': ['value']}],
            'allowedOutputSchema': 'fixture', 'maximum_decisions': 2,
            'generation_binding': release.release_sha256}


def features_for(concept, role, schema, scope):
    return (concept, role, schema, scope)


class AtlasTrainingAdapterTest(unittest.TestCase):
    def setUp(self):
        course, graph, sources, answers, _ = closed_source_fixture()
        registered = sources.require('fixture.z-generator/v1', 'fixture.z-oracle/v1')
        def draw(**kwargs):
            return tuple({**row, 'source_id': 'source-1', 'source_family_id': 'family-1', 'episode_id': 'episode-1', 'tokens': [1, 2, 1]}
                         for row in registered.draw(**kwargs))
        def check(row, **kwargs):
            gold = row.get('gold')
            if isinstance(gold, dict):
                return gold == {'decisions': ['FALSE', 'END_FRAME']}
            return registered.check(row, **kwargs)
        sources = SourceAdapterRegistry((replace(registered, draw=draw, check=check),))
        curriculum, bindings = from_legacy_course(course)
        release = compile_executable_factory_release(curriculum, bindings, CurriculumProfile.full(),
            sources, answers, source_root=None, graph=graph, verification_seed=17)
        self.context = SourceExecutionContext(release, graph, None, sources, answers)
        self.model_generation = 'fixture-model-generation'
        self.rows = self.context.draw_rows(seed=17, capability='Z.C0', each=1)

    def compile(self, rows, *, release_sha=None, encoders=None, policy='allow', generation=None, sealed=()):
        delivery = describe_delivered_teaching(self.context.release, 'Z.C0', 'source.direct/Z.C0', rows)
        return compile_training_batch(rows, self.context, {'context': 1024},
            delivery=delivery, delivery_capability='Z.C0', delivery_release_sha256=release_sha or self.context.release.release_sha256,
            teacher_strategy={'policy': 'focused'}, requested_count=3, optimizer_step_seed=42,
            rehearsal_by_id={rows[0]['id']: 'prior'}, visible_ends={rows[0]['id']: 2},
            source_ast_for=source_ast_for, compile_prefix=compile_prefix,
            feature_requests_for=feature_requests_for, features_for=features_for, answer_plan_for=lambda *args: {**answer_plan_for(*args), 'generation_binding': self.model_generation},
            frames_for_ast=frames_for_ast, check_context_eligibility=check_context_eligibility,
            eligible_source_for=eligible_source_for, task_scope='test', source_frontier='release', eligibility_policy=policy,
            target_encoders=encoders, generation_binding=generation or self.model_generation,
            sealed_holdout_ids=sealed)

    def test_real_factory_rows_and_delivery_bind_typed_source_and_target(self):
        item = self.compile(self.rows).rows[0]
        self.assertEqual(item.model_input.prefix.ast, Literal('1,2', 'TokenSequence'))
        self.assertEqual(item.model_input.features, (('1,2', 'subject', 'fixture.schema', 'public'),))
        self.assertEqual(item.target.value, 'FALSE')
        self.assertEqual(item.target.token_id, 1)
        self.assertEqual(item.model_input.eligibility_digest, 'e' * 64)
        self.assertIn(('modalityID', 'answer.binary/v1'), item.model_input.answer_plan)
        self.assertEqual(item.provenance.row_id, self.rows[0]['id'])
        self.assertEqual(item.provenance.source_id, 'source-1')
        self.assertEqual(item.provenance.requested_count, 3)
        self.assertEqual(item.provenance.delivered_count, 1)
        self.assertEqual(item.provenance.optimizer_step_seed, 42)
        self.assertEqual(item.provenance.teacher_strategy, (('policy', 'focused'),))

    def test_hidden_gold_and_future_tokens_cannot_change_model_input(self):
        first = self.compile(self.rows).rows[0]
        changed = [{**self.rows[0], 'gold': 'TRUE', 'tokens': [1, 2, 2],
                    'auxiliary_labels': {'role': 'different'},
                    'feature_requests': [('LEAKED_GOLD_TRUE', 'bad', 'bad', 'bad')]}]
        second = self.compile(changed).rows[0]
        self.assertEqual(first.model_input, second.model_input)
        self.assertNotEqual(first.target.value, second.target.value)

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

    def test_ineligible_source_is_held_before_compilation(self):
        with self.assertRaises(BilqisError):
            self.compile(self.rows, policy='deny')

    def test_native_output_is_bound_to_released_semantic_identity(self):
        row = {**self.rows[0], 'native_output': {'identity': 'cogal.value.false', 'token_id': 1}}
        item = self.compile([row]).rows[0]
        self.assertEqual(item.native_target.kind, 'semantic_token')
        self.assertEqual(item.native_target.value, 'cogal.value.false')
        self.assertEqual(item.native_target.token_id, 1)
        with self.assertRaises(BilqisError):
            self.compile([{**row, 'native_output': {'identity': 'cogal.value.true', 'token_id': 2}}])

    def test_gold_only_change_cannot_reach_input_or_features(self):
        first = self.compile(self.rows).rows[0]
        second = self.compile([{**self.rows[0], 'gold': 'TRUE', 'auxiliary_labels': {'role': 'x'}}]).rows[0]
        self.assertEqual(first.model_input, second.model_input)
        self.assertNotEqual(first.target, second.target)

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

    def test_sealed_holdout_identity_cannot_enter_training(self):
        with self.assertRaises(BilqisError):
            self.compile(self.rows, sealed=(self.rows[0]['id'],))

    def test_source_family_and_episode_independence(self):
        from bilqis_mlx.runtime.atlas_training_adapter import require_independent_cohorts
        batch = self.compile(self.rows)
        self.assertEqual(batch.rows[0].provenance.source_family_id, 'family-1')
        self.assertEqual(batch.rows[0].provenance.episode_id, 'episode-1')
        with self.assertRaises(BilqisError):
            require_independent_cohorts(batch, batch)
        sibling = self.compile([{**self.rows[0], 'id': 'other', 'source_family_id': 'family-2', 'episode_id': 'episode-2'}])
        require_independent_cohorts(batch, sibling)
        missing = self.compile([{key: value for key, value in self.rows[0].items() if key != 'source_family_id'}])
        with self.assertRaises(BilqisError):
            require_independent_cohorts(missing, sibling)

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
        self.assertEqual(first.rows, second.rows)

    def test_released_signatures_select_rules_without_grade_input(self):
        from bilqis_mlx.runtime.atlas_training_adapter import resolve_batch_rules
        batch = self.compile(self.rows)
        def signatures(release, graph, roots):
            return (('fixture.operator', 'Boolean*Boolean->Boolean'),)
        def rules(source_anchor, semantic_signatures, family):
            self.assertEqual(family, 'family-1')
            return ('boolean-rules/v1',) if semantic_signatures[0][1].startswith('Boolean') else ('integer-rules/v1',)
        first = resolve_batch_rules(batch, self.context, released_signatures_for=signatures, rule_set_for=rules)
        self.assertEqual(first.rows[0].rule_policy, ('boolean-rules/v1',))
        second = resolve_batch_rules(batch, self.context,
            released_signatures_for=lambda *args: (('fixture.operator', 'Integer*Integer->Integer'),), rule_set_for=rules)
        self.assertEqual(second.rows[0].rule_policy, ('integer-rules/v1',))
        self.assertEqual(first.rows[0].model_input, second.rows[0].model_input)

    def test_current_release_is_checked_again_at_consumption(self):
        batch = self.compile(self.rows)
        require_current_release(batch, self.context, generation_binding=self.model_generation)
        with self.assertRaises(BilqisError):
            require_current_release(replace(batch, release_sha256='f' * 64), self.context, generation_binding=self.model_generation)
        with self.assertRaises(BilqisError):
            require_current_release(batch, self.context, generation_binding='stale-generation')
        with self.assertRaises(BilqisError):
            self.compile(self.rows, generation='stale-generation')

    def test_delivery_content_tampering_is_rejected(self):
        delivery = describe_delivered_teaching(self.context.release, 'Z.C0', 'source.direct/Z.C0', self.rows)
        changed = [{**self.rows[0], 'gold': 'TRUE'}]
        with self.assertRaises(BilqisError):
            compile_training_batch(changed, self.context, {}, delivery=delivery, delivery_capability='Z.C0',
                delivery_release_sha256=self.context.release.release_sha256,
                teacher_strategy={'policy': 'focused'}, requested_count=3, optimizer_step_seed=42,
                rehearsal_by_id={}, visible_ends={}, source_ast_for=source_ast_for,
                compile_prefix=compile_prefix, feature_requests_for=feature_requests_for, features_for=features_for, answer_plan_for=lambda *args: {**answer_plan_for(*args), 'generation_binding': self.model_generation},
            frames_for_ast=frames_for_ast, check_context_eligibility=check_context_eligibility,
            eligible_source_for=eligible_source_for, task_scope='test', source_frontier='release', eligibility_policy='allow',
            generation_binding=self.model_generation)


class AtlasAdapterExecutionTest(AtlasTrainingAdapterTest):
    def test_padding_uses_actual_maximum_and_c08_partition(self):
        from bilqis_mlx.runtime.atlas_training_adapter import pad_microbatches
        batch = self.compile(self.context.draw_rows(seed=17, capability='Z.C0', each=2))
        groups = pad_microbatches(batch, {}, 100, plan_microbatches=lambda rows, topology, budget: ((0, 1),),
            indices_for_plan=lambda plan: plan,
            positions_for=lambda prefix: tuple(int(x) for x in prefix.ast.value.split(',')))
        self.assertEqual(groups[0].positions, ((1, 2, None), (1, 2, 1)))
        self.assertEqual(groups[0].padding_mask, ((True, True, False), (True, True, True)))
        with self.assertRaises(BilqisError):
            pad_microbatches(batch, {}, 100, plan_microbatches=lambda *args: ((0,),),
                indices_for_plan=lambda plan: plan, positions_for=lambda prefix: (1,))

    def test_padding_reserves_answer_decision_budget(self):
        from bilqis_mlx.runtime.atlas_training_adapter import pad_microbatches
        with self.assertRaises(BilqisError):
            pad_microbatches(self.compile(self.rows), {}, 100,
                plan_microbatches=lambda *args: ((0,),), indices_for_plan=lambda plan: plan,
                positions_for=lambda prefix: (1,) * 1024)

    def test_auxiliaries_require_evidence_and_stay_out_of_input(self):
        from bilqis_mlx.runtime.atlas_training_adapter import attach_auxiliaries
        batch = self.compile(self.rows)
        self.assertEqual(attach_auxiliaries(batch, {}, verify=lambda *args: False), batch)
        with self.assertRaises(BilqisError):
            attach_auxiliaries(batch, {self.rows[0]['id']: {'role': ('subject', 'SOURCE', 'receipt')}},
                               verify=lambda *args: False)
        result = attach_auxiliaries(batch, {self.rows[0]['id']: {'role': ('subject', 'SOURCE', 'receipt')}},
                                    verify=lambda *args: True)
        self.assertEqual(result.rows[0].model_input, batch.rows[0].model_input)
        self.assertEqual(result.rows[0].auxiliaries, (('role', 'subject', 'SOURCE', 'receipt'),))

    def test_real_observation_capture_preserves_rows_and_cost(self):
        import tempfile
        from bilqis_mlx.runtime.atlas_training_adapter import capture_realized_delivery
        from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture, read_sidecar, store_sidecar, read_observation
        batch = self.compile(self.rows)
        with tempfile.TemporaryDirectory() as root:
            capture = ObservationCapture(root, {})
            capture.attempt_id = 'fixture-attempt'
            proposal_ref = store_sidecar(root, {'attempt_id': capture.attempt_id})
            capture.proposal_id = proposal_ref['sha256']
            capture.select_option('Z.C0', None)
            capture_realized_delivery(batch, self.context, capture, 'Z.C0', 1, self.rows,
                generation_binding=batch.generation_binding, option_rows=self.rows, priority=(),
                preservation=(), support=(), enrichment=(), guidance=None, controls={}, seed=42,
                cost={'wall_seconds': 0.25})
            payload = read_sidecar(root, capture.steps[0])
            self.assertEqual(payload['controls']['realized_cost'], {'wall_seconds': 0.25})
            self.assertEqual(read_sidecar(root, payload['positions'][0]['row']), self.rows[0])
            envelope = store_sidecar(root, {'attempt_id': capture.attempt_id, 'proposal_id': capture.proposal_id,
                'proposal': proposal_ref, 'steps': capture.steps})
            observed = read_observation(root, {'teacher_observation': {'attempt_id': capture.attempt_id,
                'proposal_id': capture.proposal_id, 'envelope': envelope}})
            self.assertEqual(observed['steps'][0]['positions'][0]['row'], self.rows[0])
            self.assertEqual(observed['steps'][0]['controls']['realized_cost'], {'wall_seconds': 0.25})
            with self.assertRaises(BilqisError):
                capture_realized_delivery(batch, self.context, capture, 'Z.C0', 1,
                    [{**self.rows[0], 'gold': 'TRUE'}], generation_binding=batch.generation_binding,
                    option_rows=self.rows, priority=(), preservation=(), support=(), enrichment=(),
                    guidance=None, controls={}, seed=42, cost={'wall_seconds': 0.25})

    def test_training_and_inference_use_one_selector_without_inference_targets(self):
        from bilqis_mlx.runtime.atlas_training_adapter import execute_with_backend
        batch = self.compile(self.rows)
        selector = lambda topology: ('backend', topology['identity'])
        invoke = lambda backend, inputs, targets: (backend, inputs, targets)
        kwargs = dict(generation_binding=batch.generation_binding, model_backend=selector, invoke=invoke)
        prediction = execute_with_backend(batch, self.context, {'identity': 'fixture'}, training=False, **kwargs)
        training = execute_with_backend(batch, self.context, {'identity': 'fixture'}, training=True, **kwargs)
        self.assertEqual(prediction[:2], training[:2])
        self.assertIsNone(prediction[2])
        self.assertEqual(training[2][0][0], batch.rows[0].target)


if __name__ == '__main__':
    unittest.main()
