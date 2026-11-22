"""Issue #1504 regressions for terminal motif continuation latency."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import CandidateCustodyIdentity
from bilqis_mlx.learning._retention.tests.motif_allocation_support import (
    CandidateMotifAllocationFixture,
)
from bilqis_mlx.runtime.bamf_bundle.motif import source_continuation as continuation
from bilqis_mlx.runtime.bamf_bundle.records import CompleteStudent
from bilqis_mlx.semantics.context_eligibility import ContextHold


def _accepted_parent(manifest="a" * 64):
    topology = SimpleNamespace(digest="b" * 64)
    extents = SimpleNamespace(digest="c" * 64)
    custody = CandidateCustodyIdentity(
        "issue-1504", 0, manifest, topology.digest, extents.digest)
    retained = SimpleNamespace(custody=custody, allocations=object())
    return CompleteStudent(
        "issue-1504", 0, None, "d" * 64, topology, extents, retained,
        object(), object(), {}, {}, {}, {}, {}, {}, (), None)


def test_accepted_parent_batch_seal_does_not_reload_validated_bundle():
    parent = _accepted_parent()
    held = ContextHold(("TEST_HOLD",), (), ())
    with patch.object(
            continuation, "load_bamf_bundle",
            side_effect=AssertionError("accepted parent was cold-loaded again")), patch.object(
                continuation, "_prepare_source_qualified_motif_batch_with_parent",
                return_value=held) as prepare:
        result = continuation.seal_source_qualified_motif_batch_from_accepted_parent(
            (), accepted_parent=parent, expected_manifest_sha256="a" * 64,
            budget=object())

    assert result is held
    assert prepare.call_args.kwargs["parent"] is parent.retained_state.allocations


def test_accepted_parent_batch_seal_rejects_manifest_drift_before_planning():
    parent = _accepted_parent()
    with patch.object(
            continuation,
            "_prepare_source_qualified_motif_batch_with_parent") as prepare:
        with pytest.raises(BilqisError):
            continuation.seal_source_qualified_motif_batch_from_accepted_parent(
                (), accepted_parent=parent, expected_manifest_sha256="e" * 64,
                budget=object())
    prepare.assert_not_called()


def test_accepted_parent_single_seal_does_not_reload_validated_bundle():
    parent = _accepted_parent()
    held = ContextHold(("TEST_HOLD",), (), ())
    with patch.object(
            continuation, "load_bamf_bundle",
            side_effect=AssertionError("accepted parent was cold-loaded again")), patch.object(
                continuation, "_prepare_source_qualified_motifs_with_parent",
                return_value=held) as prepare:
        result = continuation.seal_source_qualified_motifs_from_accepted_parent(
            None, None, None, accepted_parent=parent,
            expected_manifest_sha256="a" * 64, source_root=None, graph=None,
            task_scope=None, source_frontier=None, policy=None, source_seed=0,
            source_each=0, budget=object())

    assert result is held
    assert prepare.call_args.kwargs["parent"] is parent.retained_state.allocations


def test_accepted_parent_stage_reuses_currentness_identity_without_reload_or_hash():
    fixture = CandidateMotifAllocationFixture()
    fixture.setUp()
    transaction = fixture._step()
    run_identity = SimpleNamespace(run_seed=0)
    parent = CompleteStudent(
        "fixture-run", 0, None, "d" * 64, fixture.spec, fixture.extents,
        fixture.parent, object(), object(), {}, {}, {}, {}, {}, {}, (), run_identity)
    proposed = SimpleNamespace(
        proposed=SimpleNamespace(
            manifest=SimpleNamespace(
                capacity=16384, digest=fixture.parent.allocations.manifest.digest),
            digest=fixture.parent.allocations.digest))
    source = fixture._continuation(proposed)
    currentness = SimpleNamespace(
        candidate_identity_sha256=transaction._parent_identity_sha256)
    staged = object()

    with fixture._continuation_patch(source), patch(
            "bilqis_mlx.runtime.bamf_bundle.admission.load_accepted_generation",
            side_effect=AssertionError("accepted generation was cold-loaded again")), patch(
                "bilqis_mlx.learning._atlas_candidate.identity_binding."
                "candidate_identity_for_canonical_consumer",
                side_effect=AssertionError("accepted identity was fully recomputed")), patch(
                    "bilqis_mlx.runtime.bamf_bundle.currentness_transaction."
                    "accepted_currentness_identity",
                    return_value=currentness) as identity, patch(
                            "bilqis_mlx.runtime.model_topology_v2.b01_generation_extents",
                            return_value=fixture.extents), patch(
                        "bilqis_mlx.learning._atlas_candidate.transaction."
                        "_stage_candidate_motif_allocation",
                        return_value=staged) as stage:
        result = continuation.stage_source_qualified_motif_allocation(
            "unused", transaction, source, accepted_parent=parent,
            currentness_transaction=object())

    assert result is staged
    identity.assert_called_once()
    stage.assert_called_once()
