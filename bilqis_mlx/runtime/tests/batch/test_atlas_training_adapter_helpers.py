"""Shared fixtures extracted structurally from test_atlas_training_adapter.py."""
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

class AtlasTrainingAdapterFixture(unittest.TestCase):
    """Shared setup for shards of the historical adapter test class."""

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

if __name__ == '__main__':
    unittest.main()
