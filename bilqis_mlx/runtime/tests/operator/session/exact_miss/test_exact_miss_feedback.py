"""Ordinary native exact-miss feedback, with a gold-blind fixture learner.

Use actual admitted predicate source/lowering/evaluator/rehearsal owners. The
model response is a deterministic FALSE proposal, not actual neural inference.
Currentness/cadence and numerical execution are fixture boundaries. The actual
native horizon, source packet, delivery owner, trace and C05 screen execute.
No neural student or persistent learner is trained.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest

from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.learning.teacher_visit_identity import TeacherVisitIdentity
from bilqis_mlx.runtime import accepted_priority_visit_contracts as priority
from bilqis_mlx.runtime import factory_retention_owner as owner
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger, BaselineMeasurement
from bilqis_mlx.runtime.bamf_bundle import execution_cache
from bilqis_mlx.runtime.bamf_operator.session_parts import native_session, rehearsal
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.source_prefetch import SourcePrefetchMetrics
from bilqis_mlx.runtime.bamf_operator.session_parts import pipeline
from bilqis_mlx.runtime import accepted_priority_learning_first as learning_first
from bilqis_mlx.runtime.atlas_training_delivery import capture_realized_delivery
from bilqis_mlx.runtime.retention import local_screen_stages, local_screen_support
from bilqis_mlx.runtime import _factory_parent_assessment_cache as parent_cache
from bilqis_mlx.runtime.capability_retention import CompleteSolver, EvidenceStage, DecisionStatus
from bilqis_mlx.runtime.retention.local_evaluation import (
    finalize_target_first_local_candidate,
)
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.cognitive_solver import NeuralProposal, SolveBudget, SolveContext
from bilqis_mlx.runtime.factory_complete_solver import factory_evaluation_case_from_source
from bilqis_mlx.runtime.factory_task_template import _source_task_owner, _source_view
from bilqis_mlx.runtime.retention import local_preflight as pre
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.tests.operator.pre_neural.pre_neural_journey_support import (
    LEGACY, historical_school_release,
)
from bilqis_mlx.semantics.cognitive_dag import DAGBudget
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.source_adapters.school import live_source_registry

CAPABILITIES = ('A.IDENTITY', 'A.PARENT', 'A.LINK', 'A.MEMBER', 'A.EDGE', 'A.MAPS')
PARENT = 'a' * 64
CANDIDATE = 'b' * 64


class FixtureCache(N):
    """Weak-referenceable host fixture, not an accepted learner checkpoint."""


@pytest.fixture(scope='module')
def admitted(tmp_path_factory):
    release, graph = historical_school_release()
    return SourceExecutionContext(
        release=release, graph=graph, source_root=LEGACY,
        source_registry=live_source_registry(), answer_registry=live_answer_registry(),
        run_dir=tmp_path_factory.mktemp('exact-miss-source'))


def _false_solver(source, rows, semantic_release, learned=None):
    learned = learned or {}
    bindings = {}
    for row in rows:
        _, _, execution, lowerer, _, _ = _source_task_owner(source, row)
        goal, binding = lowerer.lower(
            _source_view(row), semantic_release=semantic_release,
            source_root=source.source_root, graph=source.graph,
            release=source.release, capability=execution,
            operator_registry=source.operator_registry_for(semantic_release))
        bindings[goal.goal_id] = binding

    def context_for(goal, generation):
        binding = bindings[goal.goal_id]
        # This prediction consults only the declared Boolean answer domain.
        # It never sees evaluator gold or a gold-selected training target.
        false_handles = {item.typed.source_handle for item in binding.operands
                         if item.typed.value is learned.get(goal.goal_id, False)}
        node = goal.expression_or_holes.nodes[0]
        ref, = (item for item in node.candidate_operand_refs[0]
                if item.source_handle in false_handles)
        proposal = replace(goal, expression_or_holes=replace(
            goal.expression_or_holes, nodes=(replace(
                node, operands=(ref,), candidate_operand_refs=(), constraints=()),)))

        def propose(request):
            return NeuralProposal(proposal, request.source_binding_digest,
                                  request.generation_digest,
                                  request.unresolved_signature, 'c' * 64)

        return SolveContext(binding, neural_proposer=propose,
                            retain_validated_compositions=False)

    return CompleteSolver(context_for, SolveBudget(DAGBudget()))


def _fixture_selection(admitted, tmp_path, capability, grade, parent, cache, identity):
    release = admitted.release
    # Fixture selection is prepared before scoring, just like the native visit.
    source_seed = 17
    direct, authority = admitted.draw_bound_rows(seed=source_seed, capability=capability, each=6)
    offer = N(capability_id=capability, rows=lambda: direct, source_authority=authority,
              source_seed=source_seed, source_each=len(direct), release_sha256=release.release_sha256,
              source_binding_digest=contract_digest(release.source_bindings.by_capability[capability]),
              source_family_id=authority.source_family_id, accepted_manifest_sha256=cache.accepted_manifest_sha256,
              generation_binding=cache.generation_binding)
    authenticated = N(features=N(semantic_release=release.semantic_catalog_sha256))
    offer._planning_generation = N(_parent=parent, _cache=cache,
                                   _authenticated_features=authenticated)
    with evidence_mode(strict=False):
        selection = priority._issue_result(
            'TEACHER_SELECTED', capability, offer, N(identity=identity),
            {'lr': .001, 'depth': 1, 'distill': 0}, {}, grade, (), tmp_path, object())
    return selection, direct, authenticated


def visit_fixture(admitted, monkeypatch, tmp_path, capability, *, measured=True, peer=True):
    release = admitted.release
    semantic_release = release.semantic_catalog_sha256
    grade = admitted.execution_for(capability).grade_id
    plan = N(digest='1'*64, rubric_sha256='2'*64, source_sha256='3'*64,
             policy_epoch_sha256='4'*64, evidence_stage='FOUNDATION_ACQUISITION')
    peer_cap = next(item for item in CAPABILITIES if item != capability)
    protected = (peer_cap,) if peer else ()
    evaluated = (capability, *protected)
    target = N(target_capability_id=capability, target_grade_id=grade,
               evaluated_capability_ids=evaluated, protected_capability_ids=protected,
               evaluated_capability_groups=tuple((cap, grade) for cap in evaluated),
               evaluation_scope_sha256='6'*64,
               comparison_scope_sha256='5'*64, affected_edges=())
    parent = N(run_id='run', generation=1, retained_state=N(optimizer_step=4),
               baseline_evidence=None, correction_frontier={}, evaluation_contract={},
               implementation_sha256='1'*64, topology=N(digest='2'*64),
               extents=N(digest='3'*64), semantic_abi={}, compiler_features={},
               optimizer_hyperparameters=AdamWHyperparameters(.001, (.9, .99), 1e-8, 0))
    cache = FixtureCache(run_id='run', generation=1, accepted_manifest_sha256='8'*64, generation_binding=PARENT,
              _candidate_identity_sha256='9'*64, source_authority_registry_sha256=None)
    identity = TeacherVisitIdentity('d'*64, 1, 1, '8'*64, 'e'*64, 0,
                                    '9'*64, 0, 'cursor', capability, 'policy')
    cadence = {'phase_sha256': 'f'*64, 'run_id': 'run', 'cadence_sha256': 'a'*64,
               'authorized_capability_ids': [capability]}
    ref_rows = tuple(admitted.draw_rows(seed=2, capability=capability, each=pre.C05_PROBE_EACH))
    cases = tuple(factory_evaluation_case_from_source(
        admitted, row, semantic_release=semantic_release) for row in ref_rows)
    epoch = pre.comparison_epoch(release, plan, target, cases, parent, cache)
    if measured:
        parent.baseline_evidence = BaselineLedger((BaselineMeasurement(
            epoch.identity(capability), 'run', 1, 'a'*64, 'b'*64, 'c'*64),)).to_record()
    # A previously taught peer starts competent. This fixture's prior teacher
    # draws lawful source rows, not evaluator gold; C05 measures the peer later.
    peer_rows, peer_grant = admitted.draw_bound_rows(seed=3, capability=peer_cap, each=6)
    admitted.require_bound_rows(peer_rows, peer_grant)
    previous = {row["id"]: row["gold"] == "TRUE" for row in peer_rows} if peer else {}
    cached_rows = ((capability, 2, ref_rows),) + (((peer_cap, 3, peer_rows),) if peer else ())
    selection, direct, authenticated = _fixture_selection(
        admitted, tmp_path, capability, grade, parent, cache, identity)
    monkeypatch.setattr(priority, 'require_priority_cadence_authorization', lambda _: N(
        authorized_capability_ids=(capability,), to_record=lambda: cadence))
    monkeypatch.setattr(owner, 'bind_current_retention_protection_plan', Mock())
    monkeypatch.setattr(owner, 'bind_current_retention_source_rows', Mock())
    monkeypatch.setattr(owner, 'require_current_retention_source_rows', lambda *_: (
        plan, target, cached_rows))
    monkeypatch.setattr(owner, 'require_current_retention_plan', lambda *_: (plan, target))
    instruments = lambda _source, _parent, _path, rows, **kw: tuple(
        N(case=factory_evaluation_case_from_source(admitted, row, semantic_release=semantic_release),
          source_row=row) for row in rows)
    monkeypatch.setattr(pre, '_instruments', instruments)
    monkeypatch.setattr(local_screen_stages, '_instruments', instruments)
    monkeypatch.setattr(local_screen_support, '_instruments', instruments)
    solver_calls = []

    def solver(_source, subject, _path, instruments, **kw):
        rows = tuple(item.source_row for item in instruments)
        is_parent = subject is parent
        solver_calls.append(("parent" if is_parent else "candidate", len(rows)))
        memory = previous if is_parent else subject.memory
        return (_false_solver(admitted, rows, semantic_release, memory),
                PARENT if is_parent else CANDIDATE)

    monkeypatch.setattr(pre, 'factory_complete_solver', solver)
    monkeypatch.setattr(local_screen_stages, 'factory_complete_solver', solver)
    object.__setattr__(admitted, '_accepted_feature_context', authenticated)
    monkeypatch.setattr(execution_cache, 'AcceptedExecutionCache', FixtureCache)
    monkeypatch.setattr(execution_cache, 'require_accepted_execution_cache', lambda value: value)
    monkeypatch.setattr(parent_cache, 'require_accepted_execution_cache', lambda value: value)
    monkeypatch.setattr(native_session, 'bind_current_retention_protection_plan', Mock())
    monkeypatch.setattr(native_session, 'rejection_attempt_ordinals', lambda *_: (1, 1))
    monkeypatch.setattr(native_session, 'candidate_step_horizon', lambda *_: 1)
    monkeypatch.setattr(rehearsal, 'require_current_retention_plan', lambda *_: (plan, target))
    monkeypatch.setattr(rehearsal, 'current_structural_weaknesses', lambda *_: ())
    monkeypatch.setattr('bilqis_mlx.runtime.active_generated_grade.read_active_generated_grade',
                        lambda *_args, **_kw: N(member_capability_ids=(capability,),
                        activation_sha256='f'*64, definition=N(definition_sha256='1'*64)))
    return N(source=admitted, parent=parent, cache=cache, selection=selection,
             plan=plan, target=target, cached_rows=cached_rows, direct=direct,
             previous=previous, peer=peer_cap, solver_calls=solver_calls,
             authenticated=authenticated, run_dir=tmp_path)


def _finalize_fixture(fixture, assessments, grants):
    def finalize(_run, parent, source, _atlas, selection, target, cache, steps,
                 capture, *_args, preflight, **_kwargs):
        assert len(steps) == 1
        assert len(fixture.solver_calls) == 1
        candidate = steps[-1].transaction
        training = (tuple(sorted({g.source_family_id for g in grants})),
                    tuple(sorted({ep for g in grants for ep in g.episode_ids})))
        target_result = local_screen_stages.target_stage(
            source, parent, candidate, candidate, 'atlas', source.release,
            fixture.plan, fixture.target, training, fixture.cached_rows, cache,
            authenticated=fixture.authenticated, preflight=preflight)
        pair, coverage = target_result[3:5]
        assert target_result[-1] is None
        assert pair.parent.results == preflight.assessment.results
        assert pair.parent.cohort.cases == preflight.assessment.cohort.cases
        assert pair.parent.score(target) == (3, 6)
        assert pair.candidate.score(target) == (6, 6)
        with pytest.raises(BilqisError) as overlap:
            replace(pair.parent.cohort, evidence_stage=EvidenceStage.STRICT_GENERALIZATION)
        assert overlap.value.context['reason'] == 'BAMF_EVALUATION_TRAINING_PROVENANCE_OVERLAP'
        reference, parent_receipt, policy = local_screen_stages.reference_stage(
            source, parent, candidate, 'atlas', source.release, fixture.plan,
            fixture.target, training, fixture.cached_rows, cache, coverage,
            authenticated=fixture.authenticated)
        decision = finalize_target_first_local_candidate(
            target, policy, reference.parent.cohort, pair, reference,
            retention_protection_plan_sha256=fixture.plan.digest,
            evaluated_capability_ids=fixture.target.evaluated_capability_ids)
        assert decision.status is DecisionStatus.ELIGIBLE
        assert reference.parent.score(fixture.peer) == (6, 6)
        assert reference.candidate.score(fixture.peer) == (6, 6)
        # A separate candidate with lost previous competence must still fail.
        lost = N(memory={key: value for key, value in candidate.memory.items()
                         if key not in fixture.previous})
        regressed, reused, same_policy = local_screen_stages.reference_stage(
            source, parent, lost, 'atlas', source.release, fixture.plan,
            fixture.target, training, fixture.cached_rows, cache, coverage,
            authenticated=fixture.authenticated)
        assert not parent_receipt.reused and reused.reused
        denied = finalize_target_first_local_candidate(
            target, same_policy, regressed.parent.cohort, pair, regressed,
            retention_protection_plan_sha256=fixture.plan.digest,
            evaluated_capability_ids=fixture.target.evaluated_capability_ids)
        assert denied.status is DecisionStatus.REJECT
        assert denied.blocking_capability == fixture.peer
        assessments.append((preflight, capture.summary(), decision, denied))
        return decision

    return finalize


@pytest.mark.parametrize('capability', CAPABILITIES)
@pytest.mark.parametrize('workers', (0, 1))
def test_ordinary_native_delivery_teaches_scored_misses(
        admitted, monkeypatch, tmp_path, capability, workers):
    fixture = visit_fixture(admitted, monkeypatch, tmp_path, capability)
    # Ahead preparation is a numerical fixture boundary. The real pipeline
    # transports the same CandidateLessonRows and host-local authority.
    monkeypatch.setattr(pipeline, 'learning_first_prepare_step',
                        lambda *_: lambda _ordinal, lesson: lesson.delivered)
    delivered, assessments, grants = [], [], []

    def execute(_run, source, parent, _atlas, _feature, rows, **kwargs):
        observation = kwargs['observation']
        assert kwargs['prepared_learning_first_source_inputs'] == rows
        exact_ids = observation.controls['exact_miss_delivery_ids']
        actual = tuple(row for row in observation.preservation if row['id'] in exact_ids)
        for row in actual:
            grant = kwargs['rehearsal_authorities'][row['id']]
            source.require_bound_rows((row,), grant)
            grants.append(grant)
        grants.append(fixture.selection.offer.source_authority)
        grants.extend(grant for key, grant in kwargs["rehearsal_authorities"].items()
                      if key not in exact_ids)
        memory = dict(fixture.previous)
        # The fixture consumes actual optimizer-bound teaching labels, not gold
        # from the assessment. It represents exact learned recall only.
        for row in rows:
            memory[row['id']] = row['gold'] == 'TRUE'
        delivered.append((actual, observation))
        capture_realized_delivery(
            None, source, observation.capture, capability, observation.step, rows,
            generation_binding=PARENT, option_rows=observation.option_rows,
            priority=observation.priority, preservation=observation.preservation,
            support=observation.support, enrichment=observation.enrichment,
            guidance=observation.guidance, controls=observation.controls,
            seed=observation.seed, cost={}, prior=observation.prior,
            fresh_support=observation.fresh_support)
        return N(transaction=N(update_steps=1, memory=memory), realized_cost={})

    monkeypatch.setattr(learning_first, 'execute_factory_candidate_step', execute)
    monkeypatch.setattr(native_session, 'retention_result',
                        _finalize_fixture(fixture, assessments, grants))
    executor = ThreadPoolExecutor(max_workers=1) if workers else None
    try:
        with evidence_mode(strict=False):
            decision = native_session.execute_selected_visit(
                tmp_path, fixture.parent, admitted, 'atlas', 'feature', fixture.selection,
                fixture.cache, 1, 1, None, workers, executor, SourcePrefetchMetrics(),
                None, emit_progress=lambda *_: None, invalid=lambda reason: pytest.fail(reason))
    finally:
        if executor is not None:
            executor.shutdown()
    assert decision.status is DecisionStatus.ELIGIBLE
    assert len(delivered) == len(assessments) == 1
    actual, observation = delivered[0]
    preflight, trace, _accepted, _rejected = assessments[0]
    assert len(actual) == 3
    assert {row['id'] for row in actual} == {
        case.case_id for case, result in zip(
            preflight.assessment.cohort.cases, preflight.assessment.results, strict=True)
        if result.answer.value != case.gold.value}
    assert observation.controls['fragile_preservation_delivered'] == 0
    assert observation.controls['exact_miss_replay_delivered'] == 3
    assert trace['policy_controls'][0]['exact_miss_replay_delivered'] == 3
    assert 'weakness_class_matches' not in observation.controls
    assert fixture.solver_calls == [
        ('parent', 6), ('candidate', 6), ('parent', 12),
        ('candidate', 12), ('candidate', 12)]
