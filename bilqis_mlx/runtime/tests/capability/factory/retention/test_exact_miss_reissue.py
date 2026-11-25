"""Exact replay remains a derived, live source/assessment authorization."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace as N

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import accepted_priority_visit_contracts as priority
from bilqis_mlx.runtime.bamf_operator.session_parts import rehearsal
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts.weakness_rehearsal import GroupOffer
from bilqis_mlx.runtime.bamf_operator.session_parts.learning_trace import CandidateLearningTrace
from bilqis_mlx.runtime.bamf_operator.source_prefetch import CandidateSourceLane, SourcePrefetchMetrics
from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
from bilqis_mlx.runtime.retention import local_preflight as pre
from bilqis_mlx.runtime.tests.operator.session.exact_miss.test_exact_miss_feedback import (
    admitted, visit_fixture,
)
from bilqis_mlx.runtime import accepted_priority_candidate_execution as delivery


def _prepare(f):
    return pre.prepare_factory_target_preflight(
        f.source, f.parent, f.cache, 'atlas', f.selection, 1)


def _issue(f, prospective, ordinal=1):
    return pre.issue_exact_miss_instruction(
        prospective, f.source, f.parent, f.cache, f.selection, f.plan, f.target, ordinal)


def _plan(f, prospective=None):
    return rehearsal.compile_rehearsal_plan(
        f.run_dir, f.parent, f.cache, f.source, f.selection,
        preflight=prospective, journal_ordinal=1 if prospective else None)


def _observation(f):
    capture = CandidateLearningTrace(
        f.selection, generation=f.cache.generation,
        accepted_manifest_sha256=f.cache.accepted_manifest_sha256,
        candidate_attempt_ordinal=1, parent_optimizer_step=4)
    return FactoryDeliveryObservation(
        capture, 5, f.direct, seed=f.selection.offer.source_seed)


def _deliver(f, plan, rows, **overrides):
    inputs = dict(
        prepared_source_rows=f.direct, prepared_enrichment_rows=(),
        prepared_rehearsal_rows=(*rows.prior, *rows.preservation, *rows.retention_support),
        rehearsal_by_id=rows.by_id, rehearsal_bindings=rows.bindings_by_id,
        rehearsal_authorities=rows.authorities_by_id, observation=_observation(f),
        exact_miss_instruction=plan.exact_miss_instruction)
    inputs.update(overrides)
    return delivery._candidate_delivery_inputs(f.selection, f.source, **inputs)[-1]


def _denied(reason, operation):
    with pytest.raises(BilqisError) as error:
        operation()
    assert error.value.context['reason'] == reason


def _reselect(f, *, each=None, depth=None, metadata=None):
    """Issue a fresh fixture selection; use real owner rows and grants."""
    old = f.selection
    offer = N(**vars(old.offer))
    if each is not None:
        rows, authority = f.source.draw_bound_rows(
            seed=offer.source_seed, capability=offer.capability_id, each=each)
        offer.rows = lambda: rows
        offer.source_authority = authority
        offer.source_each = each
        f.direct = rows
    policy = old.policy
    if depth is not None:
        policy["depth"] = depth
    f.selection = priority._issue_result(
        old.status, old.option_id, offer, old.visit, policy,
        old.metadata if metadata is None else metadata, old.lesson_grade,
        old.holds, f.run_dir, old._lawful_frontier)


def test_delivery_rejects_valid_exact_grants_beyond_current_capacity(admitted, monkeypatch, tmp_path):
    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.IDENTITY')
    with evidence_mode(strict=False):
        _reselect(f, each=2)
        prospective = _prepare(f)
        plan = _plan(f, prospective)
        assert plan.weakness_capacity == 2
        actual = rehearsal.materialize_rehearsal_rows(admitted, plan, 1,
                                                      reserved_rows=f.direct)
        assert _deliver(f, plan, actual).controls['exact_miss_replay_delivered'] == 2
        excessive = rehearsal.materialize_rehearsal_rows(
            admitted, replace(plan, weakness_capacity=6), 1, reserved_rows=f.direct)
        assert len(excessive.preservation) == 3
        _denied('BAMF_C05_EXACT_MISS_DELIVERY_CAPACITY',
                lambda: _deliver(f, plan, excessive))


def test_owner_census_and_source_reissue(admitted, monkeypatch, tmp_path):
    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.IDENTITY')
    with evidence_mode(strict=False):
        prospective = _prepare(f)
        start = admitted._source_preparation_metrics.provider_draws
        plan = _plan(f, prospective)
        assert admitted._source_preparation_metrics.provider_draws - start == 1
        instruction = plan.exact_miss_instruction
        assert instruction.preflight is prospective
        assert len(instruction.pairs) == 3
        assert f.solver_calls == [('parent', 6)]
        for row, grant in instruction.pairs:
            admitted.require_bound_rows((row,), grant)
            assert grant.seed == prospective.seed
            assert grant.each == 1
        _denied('BAMF_C05_PROSPECTIVE_TARGET_INVALID',
                lambda: _issue(f, replace(prospective)))
        _denied('BAMF_C05_EXACT_MISS_AUTHORITY_DRIFT',
                lambda: _issue(f, prospective, ordinal=2))
        # A valid source grant for a correctly answered row is not a miss grant.
        correct = next(row for row in prospective.rows if row['gold'] == 'FALSE')
        full = admitted.bind_rows(prospective.rows, seed=prospective.seed,
                                  capability=f.selection.offer.capability_id, each=6)
        generic = admitted.bind_authorized_subset_rows(prospective.rows, (correct,), full)
        forged_pairs = ((correct, generic), *instruction.pairs[1:])
        forged = replace(instruction, pairs=forged_pairs,
                         digest=pre._instruction_digest(prospective, forged_pairs))
        rows = rehearsal.materialize_rehearsal_rows(admitted, plan, 1,
                                                    reserved_rows=f.direct)
        _denied('BAMF_C05_EXACT_MISS_CENSUS_DRIFT',
                lambda: _deliver(f, plan, rows, exact_miss_instruction=forged))
        _denied('BAMF_C05_EXACT_MISS_INSTRUCTION_REQUIRED',
                lambda: _deliver(f, plan, rows, exact_miss_instruction=None))
        bindings = rows.bindings_by_id
        row = rows.preservation[0]
        stripped = {**bindings, row['id']: {
            k: v for k, v in bindings[row['id']].items() if not k.startswith('exact_miss_')}}
        _denied('BAMF_C05_EXACT_MISS_DELIVERY_DRIFT',
                lambda: _deliver(f, plan, rows, rehearsal_bindings=stripped))
        classified = {**bindings, row['id']: {
            **bindings[row['id']], 'weakness_debt_key': 'fake-class'}}
        _denied('BAMF_C05_EXACT_MISS_DELIVERY_DRIFT',
                lambda: _deliver(f, plan, rows, rehearsal_bindings=classified))
        spoof = replace(_observation(f), controls={'exact_miss_replay_delivered': 0})
        _denied('BAMF_C05_EXACT_MISS_CONTROL_SPOOFED',
                lambda: _deliver(f, plan, rows, observation=spoof))
        _denied('BAMF_C05_EXACT_MISS_CONTROL_SPOOFED',
                lambda: _deliver(f, plan, rehearsal.RehearsalRows(),
                                 observation=spoof, exact_miss_instruction=None))
        stale = _observation(f)
        stale.capture.attempt_id = 'stale'
        _denied('BAMF_C05_EXACT_MISS_ATTEMPT_DRIFT',
                lambda: _deliver(f, plan, rows, observation=stale))
        tampered = {**row, 'gold': 'FALSE'}
        bad = replace(rows, preservation=(tampered, *rows.preservation[1:]))
        _denied('BAMF_C05_EXACT_MISS_DELIVERY_DRIFT',
                lambda: _deliver(f, plan, bad))
        marker = pre.exact_miss_marker(prospective)
        record = rehearsal._binding(admitted, correct, generic, role='preservation',
                                    capability=f.selection.offer.capability_id,
                                    seed=generic.seed, each=1)
        fake_rows = rehearsal.RehearsalRows(
            preservation=(correct,), bindings=({**record, **marker},),
            authorities=((correct['id'], generic),))
        _denied('BAMF_C05_EXACT_MISS_DELIVERY_DRIFT',
                lambda: _deliver(f, plan, fake_rows))
        start = admitted._source_preparation_metrics.provider_draws
        assert _deliver(f, plan, rows).controls['exact_miss_replay_delivered'] == 3
        assert admitted._source_preparation_metrics.provider_draws == start
        f.plan.digest = '0' * 64
        _denied('BAMF_C05_EXACT_MISS_AUTHORITY_DRIFT',
                lambda: _deliver(f, plan, rows))


def test_legacy_schedule_class_first_and_collision(admitted, monkeypatch, tmp_path):
    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.PARENT')
    with evidence_mode(strict=False):
        prospective = _prepare(f)
        legacy, exact = _plan(f), _plan(f, prospective)
        assert exact.schedule_identity == legacy.identity
        assert exact.identity != legacy.identity
        assert legacy.weakness_capacity == 0 and exact.weakness_capacity == 6
        for ordinal in (1, 2, 3):
            old = rehearsal.materialize_rehearsal_rows(admitted, legacy, ordinal,
                                                       reserved_rows=f.direct)
            new = rehearsal.materialize_rehearsal_rows(admitted, exact, ordinal,
                                                       reserved_rows=f.direct)
            assert old.prior == new.prior and old.retention_support == new.retention_support
            assert old.bindings == tuple(b for b in new.bindings if b['role'] != 'preservation')
        row, grant = exact.exact_miss_instruction.pairs[0]
        # Inject one legitimate source-owned structural group at the existing
        # classifier boundary: Grade A itself has no admitted classifier.
        # This exercises allocation order, not a claim of Grade A classification.
        group = GroupOffer((row,), ((row['id'], 'class'),), (row,), grant, grant.seed)
        monkeypatch.setattr(rehearsal, 'targeted_groups', lambda *a, **kw: ((group,), ()))
        full = rehearsal.materialize_rehearsal_rows(
            admitted, replace(exact, weakness_capacity=1), 1, reserved_rows=f.direct)
        assert full.preservation == (row,)
        assert full.bindings_by_id[row['id']]['weakness_debt_key'] == 'class'
        partial = rehearsal.materialize_rehearsal_rows(
            admitted, replace(exact, weakness_capacity=2), 1, reserved_rows=f.direct)
        assert partial.preservation[0] == row and len(partial.preservation) == 2
        assert len({tuple(r['tokens']) for r in partial.preservation}) == 2
        assert 'exact_miss_assessment_sha256' not in partial.bindings_by_id[row['id']]
        assert 'exact_miss_assessment_sha256' in partial.bindings_by_id[partial.preservation[1]['id']]
        monkeypatch.setattr(rehearsal, 'targeted_groups', lambda *a, **kw: ((), ()))
        blocked = rehearsal.materialize_rehearsal_rows(
            admitted, exact, 1, reserved_rows=(*f.direct, {
                **row, 'id': 'distinct-id-same-tokens'}))
        assert row not in blocked.preservation
        assert len(blocked.preservation) == 2


def test_source_packet_parity_and_no_repeat_reissue(admitted, monkeypatch, tmp_path):
    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.LINK')
    with evidence_mode(strict=False):
        prospective = _prepare(f)
        plan = _plan(f, prospective)
        original = type(admitted).bind_rows
        calls = []

        def count(context, *args, **kwargs):
            calls.append(kwargs)
            return original(context, *args, **kwargs)

        monkeypatch.setattr(type(admitted), 'bind_rows', count)
        with ThreadPoolExecutor(max_workers=1) as executor:
            serial = CandidateSourceLane(f.selection, admitted, f.parent, 2,
                                         rehearsal_plan=plan, workers=0, executor=None,
                                         metrics=SourcePrefetchMetrics())
            parallel = CandidateSourceLane(f.selection, admitted, f.parent, 2,
                                           rehearsal_plan=plan, workers=1, executor=executor,
                                           metrics=SourcePrefetchMetrics())
            assert 'exact_miss_instruction' not in parallel.pending[1][0]
            for ordinal in (1, 2):
                a, b = serial.lesson(ordinal), parallel.lesson(ordinal)
                assert a.delivered == b.delivered
                assert a.rehearsal_bindings == b.rehearsal_bindings
                assert a.rehearsal_authorities == b.rehearsal_authorities
                assert a.prefetch_identity == b.prefetch_identity
                assert a.exact_miss_instruction is b.exact_miss_instruction is plan.exact_miss_instruction
        assert not calls
        assert f.solver_calls == [('parent', 6)]
        rows = rehearsal.materialize_rehearsal_rows(admitted, plan, 1,
                                                   reserved_rows=f.direct)
    with evidence_mode(strict=True):
        _denied('BAMF_C05_EXACT_MISS_AUTHORITY_DRIFT',
                lambda: _deliver(f, plan, rows))


def test_perfect_and_nonpredicate_scope(admitted, monkeypatch, tmp_path):
    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.EDGE', measured=False)
    with evidence_mode(strict=False):
        missed = _prepare(f)
        assert missed.assessment.score("A.EDGE") == (3, 6)
        # An unearned perfect assessment still executes ordinary acquisition,
        # but has no mistaken specimen to replay.
        from bilqis_mlx.runtime.tests.operator.session.exact_miss.test_exact_miss_feedback import _false_solver, PARENT

        def perfect(source, subject, path, instruments, **kwargs):
            rows = tuple(i.source_row for i in instruments)
            return _false_solver(source, rows, f.authenticated.features.semantic_release,
                                 {row['id']: row['gold'] == 'TRUE' for row in rows}), PARENT

        monkeypatch.setattr(pre, 'factory_complete_solver', perfect)
        prospective = _prepare(f)
        assert prospective.assessment.score('A.EDGE') == (6, 6)
        assert not prospective.skip
        assert _issue(f, prospective) is None
        # The geometry boundary must decline non-predicate singleton providers.
        from bilqis_mlx.source_adapters import lesson_geometry
        monkeypatch.setattr(lesson_geometry, 'geometry_for_adapter',
                            lambda adapter: N(layout='singleton', provider='other'))
        assert _issue(f, missed) is None
