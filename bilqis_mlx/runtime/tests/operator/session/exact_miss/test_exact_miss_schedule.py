"""Ordinary replay preserves legacy source schedules and grant distinctions."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as N

import pytest

from bilqis_mlx.runtime.bamf_operator.session_parts import rehearsal
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.source_prefetch import CandidateSourceLane, SourcePrefetchMetrics
from bilqis_mlx.runtime.retention import local_preflight as pre
from bilqis_mlx.runtime.tests.capability.factory.retention.test_exact_miss_reissue import (
    admitted, visit_fixture, _prepare, _plan, _reselect, _observation, _deliver,
)
from bilqis_mlx.runtime import accepted_priority_candidate_execution as delivery


def test_deep_fresh_support_excludes_real_exact_source_ids(admitted, monkeypatch, tmp_path):
    from bilqis_mlx.runtime.bamf_operator.session_parts import fresh_support

    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.IDENTITY')
    with evidence_mode(strict=False):
        _reselect(f, depth=3)
        prospective = _prepare(f)
        legacy, exact = _plan(f), _plan(f, prospective)
        # Use the actual prospective source seed at this draw boundary. The
        # admitted predicate generator is prefix-stable across these counts.
        monkeypatch.setattr(fresh_support, '_seed', lambda *_: prospective.seed)
        candidate_rows = admitted.draw_rows(
            seed=prospective.seed, capability=f.selection.offer.capability_id,
            each=fresh_support._SOURCE_DRAW_EACH)
        eligible = {row['id'] for row, _grant in exact.exact_miss_instruction.pairs}
        assert eligible.intersection(row['id'] for row in candidate_rows)
        with ThreadPoolExecutor(max_workers=1) as executor:
            old = CandidateSourceLane(
                f.selection, admitted, f.parent, 1, rehearsal_plan=legacy,
                policy_support_enabled=True, workers=0, executor=None,
                metrics=SourcePrefetchMetrics()).lesson(1)
            for workers in (0, 1):
                lesson = CandidateSourceLane(
                    f.selection, admitted, f.parent, 1, rehearsal_plan=exact,
                    policy_support_enabled=True, workers=workers,
                    executor=executor if workers else None,
                    metrics=SourcePrefetchMetrics()).lesson(1)
                assert lesson.prior == old.prior
                assert lesson.retention_support == old.retention_support
                assert len(lesson.fresh_support) == 1
                assert {row['id'] for row in lesson.fresh_support}.isdisjoint(eligible)
                assert not ({tuple(row['tokens']) for row in lesson.fresh_support}
                            & {tuple(row['tokens']) for row in lesson.preservation})
                observation = delivery._candidate_delivery_inputs(
                    f.selection, admitted, lesson.direct, lesson.enrichment,
                    (*lesson.prior, *lesson.preservation, *lesson.retention_support),
                    lesson.rehearsal_by_id, lesson.rehearsal_bindings_by_id,
                    lesson.rehearsal_authorities_by_id, _observation(f),
                    prepared_fresh_support_rows=lesson.fresh_support,
                    fresh_support_by_id=lesson.fresh_support_by_id,
                    fresh_support_binding=lesson.fresh_support_binding,
                    fresh_support_authority=lesson.fresh_support_authority,
                    fresh_support_depth_control=lesson.fresh_support_depth_control,
                    exact_miss_instruction=lesson.exact_miss_instruction)[-1]
                assert observation.controls['exact_miss_replay_delivered'] == 3
                assert observation.controls['fresh_support_delivered'] == 1


def _class_fixture(monkeypatch, *labels):
    """Model only the classifier boundary, absent from admitted Grade A.

    Source construction, group search, exposure ordering and grants stay real.
    """
    from bilqis_mlx.runtime.bamf_operator.session_parts import weakness_rehearsal

    classes = {label: str(index + 1) * 64 for index, label in enumerate(labels)}
    debts = tuple({"weakness": {
        "evidence_kind": "SCORED_PARENT_MISS",
        "weakness_evidence_sha256": key,
        "weakness_class": {"class_sha256": key},
        "context": {"context_sha256": "context"},
        "historical_source_ids": [],
    }} for key in classes.values())
    monkeypatch.setattr(rehearsal, 'current_structural_weaknesses', lambda *_: debts)
    monkeypatch.setattr(weakness_rehearsal, 'classify_weakness',
                        lambda _adapter, _execution, row, **_: (
                            N(class_sha256=classes[row['gold']])
                            if row['gold'] in classes else None))


def test_actual_reserved_rotation_and_class_draws_keep_legacy_schedule(
        admitted, monkeypatch, tmp_path):
    from bilqis_mlx.runtime import factory_retention_owner as owner
    from bilqis_mlx.runtime.retention.protection_plan import ProtectionReason

    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.IDENTITY')
    with evidence_mode(strict=False):
        extra = 'A.LINK'
        f.target.protected_capability_ids = (f.peer, extra)
        f.target.evaluated_capability_ids += (extra,)
        f.target.evaluated_capability_groups += ((extra, 'A'),)
        f.target.affected_edges = (
            N(capability_id=f.peer, reason=ProtectionReason.PREREQUISITE),)
        cached = (*f.cached_rows, (extra, 3, admitted.draw_rows(
            seed=3, capability=extra, each=6)))
        monkeypatch.setattr(owner, 'require_current_retention_source_rows',
                            lambda *_: (f.plan, f.target, cached))
        _reselect(f, metadata={"preservation_allocation": {
            "schema": "bilqis.bamf.predicate-preservation-allocation/v1",
            "protection_plan_sha256": f.plan.digest,
            "primary_rows": 6, "reserved_rows": 2,
            "pressure": {f.peer: 0.0, extra: 1.0}}})
        _class_fixture(monkeypatch, 'TRUE')
        prospective = _prepare(f)
        legacy, exact = _plan(f), _plan(f, prospective)
        assert exact.schedule_identity == legacy.identity
        assert exact.identity != legacy.identity
        seen = set()
        for ordinal in (1, 2, 3, 4):
            old = rehearsal.materialize_rehearsal_rows(
                admitted, legacy, ordinal, reserved_rows=f.direct)
            new = rehearsal.materialize_rehearsal_rows(
                admitted, exact, ordinal, reserved_rows=f.direct)
            assert old.prior == new.prior
            assert old.retention_support == new.retention_support
            assert old.preservation
            assert new.preservation[:len(old.preservation)] == old.preservation
            assert tuple(binding for binding in new.bindings
                         if 'exact_miss_assessment_sha256' not in binding) == old.bindings
            assert all(new.authorities_by_id[row_id] == grant
                       for row_id, grant in old.authorities)
            seen.update(row['capability'] for row in (*old.prior, *old.retention_support))
            assert _deliver(f, exact, new).controls['weakness_targets_delivered'] == 1
        assert seen == {f.peer, extra}


def test_full_class_capacity_preserves_separate_grants_and_augmented_packet(
        admitted, monkeypatch, tmp_path):
    f = visit_fixture(admitted, monkeypatch, tmp_path, 'A.IDENTITY')
    with evidence_mode(strict=False):
        _reselect(f, each=2)
        _class_fixture(monkeypatch, 'TRUE', 'FALSE')
        legacy = _plan(f)
        old = rehearsal.materialize_rehearsal_rows(
            admitted, legacy, 1, reserved_rows=f.direct)
        assert len(old.preservation) == 2
        target = next(row for row in old.preservation if row['gold'] == 'TRUE')
        structural_grant = old.authorities_by_id[target['id']]
        # Obtain a different authentic owner draw containing the same specimen.
        # This finite fixture search is independent of model outputs.
        for seed in range(256):
            if seed != structural_grant.seed and any(
                    row['id'] == target['id'] for row in admitted.draw_rows(
                        seed=seed, capability='A.IDENTITY', each=6)):
                break
        else:
            pytest.fail("fixture requires a separately granted source collision")
        monkeypatch.setattr(pre, 'prospective_seed',
                            lambda *_: seed - pre.C05_FRESH_TARGET_SEED_OFFSET)
        prospective = _prepare(f)
        exact = _plan(f, prospective)
        grant = dict((row['id'], grant) for row, grant in
                     exact.exact_miss_instruction.pairs)[target['id']]
        assert grant != structural_grant
        new = rehearsal.materialize_rehearsal_rows(
            admitted, exact, 1, reserved_rows=f.direct)
        assert old == new
        observation = _deliver(f, exact, new)
        assert observation.controls['weakness_targets_delivered'] == 2
        assert 'exact_miss_replay_delivered' not in observation.controls
        old_lesson, new_lesson = (
            CandidateSourceLane(f.selection, admitted, f.parent, 1,
                                rehearsal_plan=plan, workers=0, executor=None,
                                metrics=SourcePrefetchMetrics()).lesson(1)
            for plan in (legacy, exact))
        assert old_lesson.delivered == new_lesson.delivered
        assert old_lesson.prefetch_identity != new_lesson.prefetch_identity
