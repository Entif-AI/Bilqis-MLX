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
from bilqis_mlx.semantics.core import Literal
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, frame_evidence_digest,
    member_evidence_digest,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)


def _source_context(rows, release, visible_ends, policy_mode):
    """Issue real A13 synthetic source grants for the actual visible ASTs."""
    principal, tenant = "synthetic:person", "synthetic:tenant"
    region, scope = "synthetic:region", "synthetic:task"
    schema = FrameSchema(
        "fixture:training-frame", 1, "source:factory-fixture",
        (RoleSpec("subject", ("Entity",), 1, 1),),
        "ORDERED", "synthetic")
    envelopes = {}
    grants = {}
    for row in rows:
        tokens = row.get("tokens", ())
        end = visible_ends.get(
            row.get("id"), len(tokens) if isinstance(tokens, (tuple, list)) else 0)
        if not isinstance(tokens, (tuple, list)) or not 0 < end <= len(tokens):
            continue
        ast = source_ast_for(tuple(tokens[:end]))
        if ast.value in envelopes:
            continue
        identity = "synthetic:ast:" + ast.value
        frame = make_frame_instance(
            schema, source_instance_id=identity,
            structural_path=(), source_span=SourceSpan(0, end),
            parent_occurrence_id=None,
            bindings=(RoleOccurrence(
                "subject", 0, concept=ConceptRef(
                    "fixture:entity:" + ast.value, release, 0,
                    ("Entity",), identity)),),
            causal_prefix_end=end)
        member = ContextMember("subject", 0, "source:member:" + ast.value, end)
        frame_source = "source:frame:" + ast.value
        evidence = (
            (frame_source, frame_evidence_digest(frame)),
            (member.source_handle, member_evidence_digest(frame, member)),
        )
        for handle, digest in evidence:
            grants[handle] = SourceGrant(
                handle, principal, tenant, PUBLIC_FORMAL, release, digest,
                ("TRAINING",), (region,), (scope,),
                rights_epoch=1, correction_generation=1,
                observed_at=2, effective_from=0)
        envelopes[ast.value] = ContextEligibility(
            frame_handle="frame:" + ast.value, frame=frame,
            source_handle=frame_source, members=(member,),
            principal_id=principal, tenant_id=tenant,
            purpose="TRAINING", source_regime=PUBLIC_FORMAL,
            semantic_release=release, jurisdiction=region,
            scope=scope, join_class=PUBLIC_FORMAL,
            policy_epoch=1, rights_epoch=1,
            correction_generation=1, observed_at=2,
            effective_from=0, effective_until=None,
            causal_prefix_end=end)
    prefix = max((item.causal_prefix_end for item in envelopes.values()), default=1)
    task = TaskScope(
        principal, tenant, "TRAINING", release, region, scope,
        observed_frontier=3, effective_time=5, causal_prefix_end=prefix)
    allowed_purposes = ("TRAINING",) if policy_mode == "allow" else ("SERVING",)
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        allowed_purposes, (PUBLIC_FORMAL,), (region,), (scope,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),))
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants.values(), key=lambda item: item.source_handle)))
    def frames_for_ast(ast):
        item = envelopes.get(ast.value)
        return (item,) if item is not None else ()
    return frames_for_ast, task, frontier, policy


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

    def compile(self, rows, *, release_sha=None, encoders=None, policy='allow',
                generation=None, sealed=(), context_mutator=None,
                frames_override=None, extra_kwargs=None):
        delivery = describe_delivered_teaching(self.context.release, 'Z.C0', 'source.direct/Z.C0', rows)
        visible_ends = {rows[0]['id']: 2}
        frames_for_ast, task, frontier, context_policy = _source_context(
            rows, self.context.release.release_sha256, visible_ends, policy)
        if context_mutator is not None:
            task, frontier, context_policy = context_mutator(
                task, frontier, context_policy)
        if frames_override is not None:
            frames_for_ast = frames_override
        return compile_training_batch(rows, self.context, {'context': 1024},
            delivery=delivery, delivery_capability='Z.C0', delivery_release_sha256=release_sha or self.context.release.release_sha256,
            teacher_strategy={'policy': 'focused'}, requested_count=3, optimizer_step_seed=42,
            rehearsal_by_id={rows[0]['id']: 'prior'}, visible_ends=visible_ends,
            source_ast_for=source_ast_for, compile_prefix=compile_prefix,
            feature_requests_for=feature_requests_for, features_for=features_for, answer_plan_for=lambda *args: {**answer_plan_for(*args), 'generation_binding': self.model_generation},
            frames_for_ast=frames_for_ast, task_scope=task,
            source_frontier=frontier, eligibility_policy=context_policy,
            target_encoders=encoders, generation_binding=generation or self.model_generation,
            sealed_holdout_ids=sealed, **(extra_kwargs or {}))
