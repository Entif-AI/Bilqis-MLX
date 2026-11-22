"""Exact invalidation rules for the process-live A09 planning cache."""
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.priority_planning_owner import (
    _accepted_credit_key,
    _snapshot_key,
    _static_key,
)


def _receipt(*, generation_manifest: str, acceptance: str):
    return SimpleNamespace(
        source_atlas_bundle_id="b" * 64,
        source_release_sha256="c" * 64,
        source_source_bundle_id="d" * 64,
        generation_manifest_sha256=generation_manifest,
        acceptance_sha256=acceptance,
    )


def test_source_release_key_ignores_accepted_generation_identity():
    current = SimpleNamespace(release_sha256="a" * 64)
    selection = SimpleNamespace(
        bundle_id="b" * 64,
        release_sha256="c" * 64,
        source_bundle_id="d" * 64,
    )
    source = SimpleNamespace(
        frontier={"rights": 1},
        policy={"policy": 1},
        authority_registry_sha256="e" * 64,
    )
    first = _receipt(generation_manifest="1" * 64, acceptance="2" * 64)
    successor = _receipt(generation_manifest="3" * 64, acceptance="4" * 64)
    with patch(
            "bilqis_mlx.semantics.domains.contract_digest",
            side_effect=lambda value: repr(value)):
        frontier_identity = ("f" * 64, "0" * 64, "a" * 64, "1" * 64, "2" * 64)
        first_static = _static_key(
            current, selection, first, source, frontier_identity)
        successor_static = _static_key(
            current, selection, successor, source, frontier_identity)

    assert first_static == successor_static
    assert _snapshot_key(first_static, first) != _snapshot_key(
        successor_static, successor)


def test_source_release_key_changes_with_source_authority():
    current = SimpleNamespace(release_sha256="a" * 64)
    selection = SimpleNamespace(
        bundle_id="b" * 64,
        release_sha256="c" * 64,
        source_bundle_id="d" * 64,
    )
    receipt = _receipt(generation_manifest="1" * 64, acceptance="2" * 64)
    first = SimpleNamespace(
        frontier={"rights": 1},
        policy={"policy": 1},
        authority_registry_sha256="e" * 64,
    )
    changed = SimpleNamespace(
        frontier={"rights": 2},
        policy={"policy": 1},
        authority_registry_sha256="e" * 64,
    )
    with patch(
            "bilqis_mlx.semantics.domains.contract_digest",
            side_effect=lambda value: repr(value)):
        frontier_identity = ("f" * 64, "0" * 64, "a" * 64, "1" * 64, "2" * 64)
        assert _static_key(
            current, selection, receipt, first, frontier_identity) != _static_key(
                current, selection, receipt, changed, frontier_identity)


def test_source_release_key_changes_with_candidate_frontier_trust_identity():
    current = SimpleNamespace(release_sha256="a" * 64)
    selection = SimpleNamespace(
        bundle_id="b" * 64,
        release_sha256="c" * 64,
        source_bundle_id="d" * 64,
    )
    receipt = _receipt(generation_manifest="1" * 64, acceptance="2" * 64)
    source = SimpleNamespace(
        frontier={"rights": 1},
        policy={"policy": 1},
        authority_registry_sha256="e" * 64,
    )
    first = ("f" * 64, "0" * 64, "a" * 64, "1" * 64, "2" * 64)
    changed = ("9" * 64, "0" * 64, "a" * 64, "1" * 64, "2" * 64)
    with patch(
            "bilqis_mlx.semantics.domains.contract_digest",
            side_effect=lambda value: repr(value)):
        assert _static_key(
            current, selection, receipt, source, first) != _static_key(
                current, selection, receipt, source, changed)


def test_accepted_credit_key_uses_public_semantic_fields_not_issuance_sentinel():
    from bilqis_mlx.factory.atlas_delta_adapter_support import (
        _issue_accepted_obligation_credit,
    )

    first = _issue_accepted_obligation_credit(
        "a" * 64, "b" * 64, (("sense:one", "c" * 64),))
    changed = _issue_accepted_obligation_credit(
        "a" * 64, "d" * 64, (("sense:one", "c" * 64),))

    first_key = _accepted_credit_key(first)
    assert isinstance(first_key, str) and len(first_key) == 64
    assert first_key != _accepted_credit_key(changed)
