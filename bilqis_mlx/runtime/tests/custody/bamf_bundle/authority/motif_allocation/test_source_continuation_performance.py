"""Issue #1504 regressions for terminal motif continuation latency."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import CandidateCustodyIdentity
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
