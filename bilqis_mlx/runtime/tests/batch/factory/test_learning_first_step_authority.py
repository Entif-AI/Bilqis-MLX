"""Learning-first O(1) step authority regression tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import bilqis_mlx.runtime.atlas_model  # noqa: F401 - completes backbone import cycle
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import atlas_model_training
from bilqis_mlx.runtime.backbone_identity import require_execution_generation_binding
from bilqis_mlx.runtime.candidate import step_authority


class _Optimizer:
    def __init__(self, label):
        self.parameters = {"p": object(), "label": label}


class _Student:
    pass


class _Candidate:
    pass


class _Cache:
    pass


def _fixture():
    optimizer = _Optimizer("parent")
    state = SimpleNamespace(optimizer=optimizer, optimizer_step=7)
    parent = _Student()
    parent.retained_state = state
    parent.topology = SimpleNamespace(digest="1" * 64)
    parent.extents = SimpleNamespace(digest="2" * 64)
    cache = _Cache()
    cache.run_id = "run"
    cache.generation = 3
    cache.accepted_manifest_sha256 = "3" * 64
    cache.generation_binding = "4" * 64
    cache._candidate_identity_sha256 = "5" * 64
    cache.source_authority_registry_sha256 = "6" * 64
    source = SimpleNamespace(release=SimpleNamespace(release_sha256="7" * 64))
    return parent, cache, source


def _patch_types(cache):
    return (
        patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache", return_value=cache),
        patch("bilqis_mlx.runtime.bamf_bundle.records.CompleteStudent", _Student),
        patch(
            "bilqis_mlx.learning._atlas_candidate.transaction.CandidateTransaction",
            _Candidate),
    )


def test_latest_step_token_is_o1_and_revokes_previous_epoch():
    step_authority._reset_learning_first_step_authority_for_tests()
    parent, cache, source = _fixture()
    patches = _patch_types(cache)
    with patches[0], patches[1], patches[2]:
        first = step_authority.issue_learning_first_step_authority(
            cache, parent, None, source)
        assert step_authority.require_learning_first_step_authority(
            first, parameters=parent.retained_state.optimizer.parameters,
            topology_digest=parent.topology.digest,
            extents_digest=parent.extents.digest).speculative is False
        second = step_authority.issue_learning_first_step_authority(
            cache, parent, None, source)

    assert first != second
    with pytest.raises(BilqisError):
        step_authority.require_learning_first_step_authority(first)
    # Ordinary authority is a correctness fence, not a telemetry surface.
    # Issuing/requiring tokens must not manufacture hot-path accounting.
    assert not any(step_authority.learning_first_step_authority_metrics_snapshot().values())


def test_speculative_token_cannot_validate_accepted_parent_parameters():
    step_authority._reset_learning_first_step_authority_for_tests()
    parent, cache, source = _fixture()
    candidate = _Candidate()
    candidate.learning_first = True
    candidate.parent = parent.retained_state
    candidate.update_steps = 1
    candidate.optimizer = _Optimizer("candidate")
    patches = _patch_types(cache)
    with patches[0], patches[1], patches[2]:
        token = step_authority.issue_learning_first_step_authority(
            cache, parent, candidate, source)
        authority = step_authority.require_learning_first_step_authority(
            token, parameters=candidate.optimizer.parameters)
        assert authority.speculative is True
        with pytest.raises(BilqisError):
            step_authority.require_learning_first_step_authority(
                token, parameters=parent.retained_state.optimizer.parameters)


def test_unchanged_candidate_reuses_token_and_update_reissues_it():
    step_authority._reset_learning_first_step_authority_for_tests()
    parent, cache, source = _fixture()
    candidate = _Candidate()
    candidate.learning_first = True
    candidate.parent = parent.retained_state
    candidate.update_steps = 1
    candidate.optimizer = _Optimizer("candidate")
    patches = _patch_types(cache)
    with patches[0], patches[1], patches[2]:
        first = step_authority.issue_learning_first_step_authority(
            cache, parent, candidate, source)
        reused = step_authority.bind_learning_first_step_authority(
            cache, parent, candidate, source)
        candidate2 = _Candidate()
        candidate2.learning_first = True
        candidate2.parent = parent.retained_state
        candidate2.update_steps = 2
        candidate2.optimizer = _Optimizer("candidate-2")
        second = step_authority.issue_learning_first_step_authority(
            cache, parent, candidate2, source)

    assert reused == first
    assert second != first
    with pytest.raises(BilqisError):
        step_authority.require_learning_first_step_authority(first)
    assert step_authority.require_learning_first_step_authority(
        second, parameters=candidate2.optimizer.parameters).candidate_step == 2


def test_learning_first_gradient_rebinding_never_falls_back_to_full_parameter_hash():
    step_authority._reset_learning_first_step_authority_for_tests()
    parent, cache, source = _fixture()
    patches = _patch_types(cache)
    with patches[0], patches[1], patches[2]:
        token = step_authority.issue_learning_first_step_authority(
            cache, parent, None, source)
        parameters = parent.retained_state.optimizer.parameters
        with patch.object(
                atlas_model_training, "issue_execution_generation_binding",
                side_effect=AssertionError("full execution-generation proof")):
            rebind = atlas_model_training._gradient_execution_rebinder(
                parameters, None, spec=parent.topology, extents=parent.extents,
                generation=token)

    traced = {"trace": object()}
    binding = rebind(traced)
    assert require_execution_generation_binding(
        binding, traced, spec=parent.topology,
        extents=parent.extents).generation_digest == token
    metrics = step_authority.learning_first_step_authority_metrics_snapshot()
    assert metrics["learning_first_step_full_proof_fallbacks"] == 0


@pytest.mark.parametrize("drift", (
    "accepted_generation",
    "accepted_manifest",
    "accepted_generation_binding",
    "accepted_candidate_identity",
    "source_authority_registry",
    "release",
    "topology",
    "extents",
    "optimizer_lineage",
))
def test_governing_identity_drift_invalidates_current_step_token(drift):
    step_authority._reset_learning_first_step_authority_for_tests()
    parent, cache, source = _fixture()
    patches = _patch_types(cache)
    with patches[0], patches[1], patches[2]:
        token = step_authority.issue_learning_first_step_authority(
            cache, parent, None, source)

    if drift == "accepted_generation":
        cache.generation += 1
    elif drift == "accepted_manifest":
        cache.accepted_manifest_sha256 = "8" * 64
    elif drift == "accepted_generation_binding":
        cache.generation_binding = "8" * 64
    elif drift == "accepted_candidate_identity":
        cache._candidate_identity_sha256 = "8" * 64
    elif drift == "source_authority_registry":
        cache.source_authority_registry_sha256 = "8" * 64
    elif drift == "release":
        source.release.release_sha256 = "8" * 64
    elif drift == "topology":
        parent.topology.digest = "8" * 64
    elif drift == "extents":
        parent.extents.digest = "8" * 64
    elif drift == "optimizer_lineage":
        parent.retained_state.optimizer = _Optimizer("other")

    with pytest.raises(BilqisError):
        step_authority.require_learning_first_step_authority(token)


def test_bound_candidate_drift_fails_closed_instead_of_reissuing():
    step_authority._reset_learning_first_step_authority_for_tests()
    parent, cache, source = _fixture()
    candidate = _Candidate()
    candidate.learning_first = True
    candidate.parent = parent.retained_state
    candidate.update_steps = 1
    candidate.optimizer = _Optimizer("candidate")
    patches = _patch_types(cache)
    with patches[0], patches[1], patches[2]:
        first = step_authority.issue_learning_first_step_authority(
            cache, parent, candidate, source)
        source.release.release_sha256 = "8" * 64
        with pytest.raises(BilqisError):
            step_authority.bind_learning_first_step_authority(
                cache, parent, candidate, source)

    assert not any(step_authority.learning_first_step_authority_metrics_snapshot().values())
    assert first not in (None, "")
