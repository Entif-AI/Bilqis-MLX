"""Structural test shard from test_atlas_training_adapter.py; assertions preserved."""
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
from bilqis_mlx.semantics.core import Literal
from bilqis_mlx.runtime.tests.batch.test_atlas_training_adapter_helpers import (answer_plan_for, check_context_eligibility, compile_prefix, eligible_source_for, feature_requests_for, features_for, frames_for_ast, source_ast_for)

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
