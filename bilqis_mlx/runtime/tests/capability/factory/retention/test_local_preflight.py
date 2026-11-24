"""Prospective assessment behavior with deterministic complete-solver fixtures."""
from dataclasses import replace
from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.teacher_visit_identity import TeacherVisitIdentity
from bilqis_mlx.runtime import factory_retention_owner as owner
from bilqis_mlx.runtime import accepted_priority_visit_contracts as priority
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger, BaselineMeasurement
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.retention import local_preflight as pre
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import _cases, _solver, PARENT


def _fixture(monkeypatch, measured, perfect):
    cases, contexts = _cases('target', 'grade', pre.C05_PROBE_EACH, 'fresh')
    rows = tuple({'id': c.case_id, 'capability': 'target',
                  'source_family_id': 'family', 'episode_id': c.case_id} for c in cases)
    plan = N(digest='1'*64, rubric_sha256='2'*64, source_sha256='3'*64,
             policy_epoch_sha256='4'*64, evidence_stage='FOUNDATION_ACQUISITION')
    target = N(target_capability_id='target', target_grade_id='grade',
               evaluated_capability_ids=('target',), protected_capability_ids=(),
               comparison_scope_sha256='5'*64)
    release = N(release_sha256='6'*64, semantic_catalog_sha256='7'*64)
    parent = N(run_id='run', generation=1, retained_state=N(optimizer_step=4),
               baseline_evidence=None, correction_frontier={}, evaluation_contract={})
    cache = N(accepted_manifest_sha256='8'*64, generation_binding=PARENT,
              _candidate_identity_sha256='9'*64, source_authority_registry_sha256=None)
    epoch = pre.comparison_epoch(release, plan, target, cases, parent, cache)
    if measured:
        parent.baseline_evidence = BaselineLedger((BaselineMeasurement(
            epoch.identity('target'), 'run', 1, 'a'*64, 'b'*64, 'c'*64),)).to_record()
    identity = TeacherVisitIdentity('d'*64, 1, 1, '8'*64, 'e'*64, 0,
                                    '9'*64, 0, 'cursor', 'target', 'policy')
    cadence = {'phase_sha256': 'f'*64, 'run_id': 'run', 'cadence_sha256': 'a'*64,
               'authorized_capability_ids': ['target']}
    selection = N(status='TEACHER_SELECTED', visit=N(identity=identity))
    monkeypatch.setattr(priority, 'require_priority_cadence_authorization', lambda _: N(
        authorized_capability_ids=('target',), to_record=lambda: cadence))
    monkeypatch.setattr(owner, 'bind_current_retention_protection_plan', Mock())
    monkeypatch.setattr(owner, 'bind_current_retention_source_rows', Mock())
    monkeypatch.setattr(owner, 'require_current_retention_source_rows', lambda *_: (
        plan, target, (('target', 2, rows),)))
    monkeypatch.setattr(pre, 'factory_evaluation_case_from_source', lambda _, row, **kw: next(
        c for c in cases if c.case_id == row['id']))
    monkeypatch.setattr(pre, '_instruments', lambda *a, **kw: tuple(N(case=c) for c in cases))
    solver = Mock(return_value=(_solver(contexts, {c.case_id for c in cases[:len(cases) if perfect else 1]}), PARENT))
    monkeypatch.setattr(pre, 'factory_complete_solver', solver)
    source = N(release=release, draw_rows=lambda **kw: rows,
               _accepted_feature_context=N(features=N(semantic_release='7'*64)))
    with evidence_mode(strict=False):
        issued = pre.prepare_factory_target_preflight(source, parent, cache, 'artifact', selection, 1)
    return issued, parent, cache, release, plan, target, solver


@pytest.mark.parametrize('measured,perfect,skip', [(True, True, True), (False, True, False), (True, False, False)])
def test_only_measured_perfect_target_skips(monkeypatch, measured, perfect, skip):
    issued, parent, cache, release, plan, target, solver = _fixture(monkeypatch, measured, perfect)
    assert issued.skip is skip
    assert solver.call_count == 1
    if not skip:
        cohort = replace(issued.assessment.cohort, training_family_ids=('delivered',),
                         training_episode_ids=('delivered-episode',))
        reused = pre.reuse_parent_assessment(issued, parent, cache, release, plan, target,
                                            cohort, issued.coverage)
        assert reused.results == issued.assessment.results
        assert reused.cohort == cohort
        assert solver.call_count == 1
        with pytest.raises(BilqisError):
            pre.reuse_parent_assessment(issued, parent, cache, release, plan, target,
                                        replace(cohort, rubric_sha256='0'*64), issued.coverage)


def test_seed_changes_only_with_attempt_identity_and_unissued_token_fails(monkeypatch):
    issued, _, _, release, plan, target, _ = _fixture(monkeypatch, True, False)
    seed = pre.prospective_seed(release, issued.visit, issued.cadence, 1, plan, target)
    assert seed == pre.prospective_seed(release, issued.visit, issued.cadence, 1, plan, target)
    assert seed != pre.prospective_seed(release, issued.visit, issued.cadence, 2, plan, target)
    assert seed != pre.prospective_seed(release, issued.visit, {'phase_sha256': '0'*64}, 1, plan, target)
    with pytest.raises(BilqisError):
        pre.require_preflight(replace(issued))


def test_skip_receipt_replays_neutrally_from_real_journal_and_cas(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from bilqis_mlx.data_plane import DataPlane
    from bilqis_mlx.learning.teacher_visit_identity import record_teacher_visit_receipt
    from bilqis_mlx.runtime import active_grade_cadence_custody, active_grade_cadence_replay
    from bilqis_mlx.runtime.bamf_bundle.publication import preflight as journal
    issued, parent, cache, _, _, _, _ = _fixture(monkeypatch, True, True)
    parent.run_identity = N(digest=issued.visit.run_identity_sha256, run_seed=1)
    parent.teacher_state = {'next_seed': 0, 'cursor': 'cursor'}
    parent.parent_manifest_sha256 = 'a'*64
    parent.outbox = ()
    parent.retained_state.custody = N(manifest_sha256=cache.accepted_manifest_sha256)
    # The deterministic assessment fixture uses a stand-in for authenticated bundle
    # hydration, but the C03 receipt, event identity, CAS and replay are real.
    pointer = {'run_id': 'run', 'generation': 1, 'manifest_sha256': cache.accepted_manifest_sha256,
               'acceptance_sha256': 'b'*64}
    (tmp_path / 'bamf-state.json').write_text('{}')
    plane = DataPlane(tmp_path / 'plane.sqlite3')
    monkeypatch.setattr('bilqis_mlx.data_plane.data_plane', lambda: plane)
    monkeypatch.setattr(journal, 'data_plane', lambda: plane)
    monkeypatch.setattr('bilqis_mlx.learning._atlas_candidate.identity_binding.'
                        'candidate_identity_for_canonical_consumer', lambda _: '9'*64)
    monkeypatch.setattr(journal, '_pointer_lock', lambda _: nullcontext())
    monkeypatch.setattr(journal, '_read_pointer', lambda _: pointer)
    monkeypatch.setattr(journal, '_live_bundle_manifest', lambda *_: {'optimizer': {'step': 4}})
    monkeypatch.setattr(active_grade_cadence_custody, 'read_current_cadence',
                        lambda _: N(cadence_sha256='a'*64))
    monkeypatch.setattr(active_grade_cadence_replay, '_accepted_chain', lambda _: {1: (parent, cache.accepted_manifest_sha256)})
    monkeypatch.setattr(active_grade_cadence_replay, '_current_accepted', lambda _: (pointer, parent))
    try:
        record_teacher_visit_receipt(issued.visit)
        receipt = journal.record_perfect_target_skip(tmp_path, parent, issued)
        assert journal.record_perfect_target_skip(tmp_path, parent, issued) == receipt
        events = plane.indexed_event_tail(tmp_path, terminal_generation=1)['events']
        assert len(events) == 1
        assert events[0]['event'] == journal.EVENT
        assert journal.authenticate_perfect_target_skip(events[0], parent, cache.accepted_manifest_sha256)['parent_correct'] == pre.C05_PROBE_EACH
        assert active_grade_cadence_replay.rebuild_authenticated_cadence_attempts(tmp_path) == ((issued.cadence, 'target', journal.PERFECT_TARGET_SKIPPED),)
        with pytest.raises(BilqisError):
            journal.authenticate_perfect_target_skip({**events[0], 'optimizer_step': 5}, parent, cache.accepted_manifest_sha256)
    finally:
        plane.close()
