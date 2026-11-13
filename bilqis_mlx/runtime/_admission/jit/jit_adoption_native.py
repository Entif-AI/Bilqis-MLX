"""Native A02 staging, retry, and publication for JIT adoption."""
from __future__ import annotations

from pathlib import Path

from .atlas_lease_contracts import _invalid, _sha


def _authenticate_native_staged_candidate(run_dir: Path, staged):
    """Bind one owner-issued A02 handoff to the live accepted B13 parent."""
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.runtime.bamf_bundle import (
        BamfBundleCandidate, load_bamf_generation_authority,
        read_accepted_generation_feature_receipt,
        require_issued_a02_staged_vocabulary_extension,
    )

    if not isinstance(run_dir, Path):
        _invalid("BAMF_ATLAS_NATIVE_STAGING_ARGUMENT_INVALID")
    staged = require_issued_a02_staged_vocabulary_extension(staged)
    candidate = staged.candidate
    receipt = staged.receipt
    expected_candidate_identity_sha256 = receipt.candidate_identity_sha256
    expected_parent_feature_receipt_sha256 = receipt.parent_feature_receipt_sha256
    if (type(candidate) is not BamfBundleCandidate
            or not _sha(expected_candidate_identity_sha256)
            or not _sha(expected_parent_feature_receipt_sha256)):
        _invalid("BAMF_ATLAS_NATIVE_STAGING_ARGUMENT_INVALID")

    pointer = run_dir / "bamf-state.json"
    parent, parent_manifest_sha256 = load_bamf_generation_authority(pointer)
    parent_feature = read_accepted_generation_feature_receipt(pointer)
    parent_state = parent.retained_state
    state = candidate.retained_state
    transition = dict(candidate.transition)

    if (parent_feature.generation_manifest_sha256 != parent_manifest_sha256
            or parent_feature.digest != expected_parent_feature_receipt_sha256):
        _invalid("BAMF_ATLAS_ACCEPTED_PARENT_FEATURE_DRIFT")
    if (parent.run_identity is None
            or candidate.run_identity != parent.run_identity
            or candidate.run_id != parent.run_id
            or candidate.generation != parent.generation + 1
            or candidate.parent_manifest_sha256 != parent_manifest_sha256
            or candidate.implementation_sha256 != parent.implementation_sha256
            or candidate.topology != parent.topology
            or candidate.optimizer_hyperparameters != parent.optimizer_hyperparameters
            or candidate.provenance != parent.provenance
            or dict(candidate.compiler_features) != dict(parent.compiler_features)
            or dict(candidate.correction_frontier) != dict(parent.correction_frontier)
            or dict(candidate.teacher_state) != dict(parent.teacher_state)
            or dict(candidate.evaluation_contract) != dict(parent.evaluation_contract)):
        _invalid("BAMF_ATLAS_ACCEPTED_PARENT_DRIFT")
    if (transition != {
            "schema": "bilqis.mlx.bamf-generation-transition/v1",
            "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True,
    } or state.optimizer_step != parent_state.optimizer_step
            or state.allocations != parent_state.allocations
            or state.step_proofs != parent_state.step_proofs
            or candidate_identity_digest(state) != expected_candidate_identity_sha256):
        _invalid("BAMF_ATLAS_NATIVE_STAGING_DRIFT")
    return candidate


def _accepted_native_retry(
        run_dir: Path, candidate, *, candidate_identity: str,
        parent_feature: str, staging_digest: str, atlas_lease,
        proposal, selected):
    """Return an exact previously published C07 pointer, or None for first publish."""
    from bilqis_mlx.learning.atlas_candidate import CandidateCustodyIdentity
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.runtime import checkpoint_outbox
    from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
        accepted_binding_for_manifest, accepted_generation,
    )
    from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
        ParsedAtlasAdmissionBinding,
    )
    from bilqis_mlx.runtime.bamf_bundle.records import BamfBundleCandidate
    from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
        initial_generation_candidate_identity_digest,
    )
    from bilqis_mlx.runtime.bamf_bundle.vocabulary.compiler_binding import (
        parameter_extension_inert_compiler_state,
        verify_parameter_extension_compiler_state,
    )
    from bilqis_mlx.semantics.domains import contract_digest

    pointer, accepted = accepted_generation(run_dir / "bamf-state.json")
    if accepted.generation < candidate.generation:
        return None
    if accepted.generation != candidate.generation:
        _invalid("BAMF_ATLAS_NATIVE_RETRY_DRIFT")
    accepted_state = accepted.retained_state
    accepted_custody = accepted_state.custody
    expected_outbox = tuple(checkpoint_outbox.with_delivery_outbox(
        {"run_id": candidate.run_id, "generation": candidate.generation},
        candidate.outbox,
    )["delivery_outbox"])
    historical_compiler = (
        dict(accepted.compiler_features) == dict(candidate.compiler_features))
    if historical_compiler:
        expected_published = candidate
    else:
        from dataclasses import replace
        if (parameter_extension_inert_compiler_state(accepted.compiler_features)
                != parameter_extension_inert_compiler_state(candidate.compiler_features)):
            _invalid("BAMF_ATLAS_NATIVE_RETRY_DRIFT")
        verify_parameter_extension_compiler_state(
            accepted.compiler_features, selected.successor)
        expected_published = replace(
            candidate, compiler_features=dict(accepted.compiler_features))
    if (type(candidate) is not BamfBundleCandidate
            or initial_generation_candidate_identity_digest(accepted)
               != initial_generation_candidate_identity_digest(expected_published)
            or accepted.outbox != expected_outbox
            or candidate_identity_digest(accepted_state) != candidate_identity
            or type(accepted_custody) is not CandidateCustodyIdentity
            or accepted_custody.run_id != accepted.run_id
            or accepted_custody.generation != accepted.generation
            or accepted_custody.manifest_sha256 != pointer["manifest_sha256"]
            or accepted_custody.topology_digest != candidate.topology.digest
            or accepted_custody.extents_digest != candidate.extents.digest):
        _invalid("BAMF_ATLAS_NATIVE_RETRY_DRIFT")
    binding = accepted_binding_for_manifest(
        run_dir, pointer["manifest_sha256"], accepted,
        expected_acceptance_sha256=pointer["acceptance_sha256"])
    if (not isinstance(binding, ParsedAtlasAdmissionBinding)
            or binding.candidate_identity_sha256 != candidate_identity
            or binding.parent_feature_receipt_sha256 != parent_feature
            or binding.staging_receipt_sha256 != staging_digest
            or binding.lease_sha256 != atlas_lease.digest()
            or binding.source_approval_sha256
            != contract_digest(atlas_lease.source_approval)
            or binding.proposal_sha256 != proposal.proposal_sha256
            or binding.factory_release_sha256 != selected.successor.release_sha256):
        _invalid("BAMF_ATLAS_NATIVE_RETRY_DRIFT")
    return pointer


def _publish_native_staged_candidate(
        runtime, selected, proposal, native_staged, atlas_lease,
        source_authority, *, current, checkpoint):
    """Publish the exact A02 state after C07 and B13 authority replay."""
    from . import state as runtime_state
    from bilqis_mlx.runtime.atlas_admission import (
        read_accepted_atlas_factory_release, read_accepted_atlas_lease,
    )
    from bilqis_mlx.runtime.bamf_bundle import (
        load_bamf_generation_authority, publish_atlas_admission_generation,
        require_issued_a02_staged_vocabulary_extension,
        require_staged_vocabulary_admission_headroom,
    )
    from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
        _issue_atlas_admission_binding,
    )
    from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
    from . import admission as runtime_admission
    from bilqis_mlx.semantics.domains import contract_digest

    native_staged = require_issued_a02_staged_vocabulary_extension(native_staged)
    candidate = native_staged.candidate
    staging_receipt = native_staged.receipt
    candidate_identity = staging_receipt.candidate_identity_sha256
    parent_feature = staging_receipt.parent_feature_receipt_sha256
    staging_digest = staging_receipt.digest

    persisted = read_accepted_atlas_lease(
        runtime.run_dir, source_authority=source_authority)
    if persisted is None or persisted != atlas_lease:
        _invalid("BAMF_ATLAS_PERSISTED_LEASE_REQUIRED")
    retry_pointer = _accepted_native_retry(
        runtime.run_dir, candidate, candidate_identity=candidate_identity,
        parent_feature=parent_feature, staging_digest=staging_digest,
        atlas_lease=atlas_lease, proposal=proposal, selected=selected)
    if retry_pointer is not None:
        release_file = runtime_admission._persist_executable_factory_release(
            runtime.run_dir, selected.successor)
        expected_release_file = (
            "factory-releases/" + selected.successor.release_sha256 + ".json")
        if release_file != expected_release_file:
            _invalid("BAMF_ATLAS_FACTORY_RELEASE_DURABLE_DRIFT")
        accepted_release = read_accepted_atlas_factory_release(runtime.run_dir)
        if accepted_release.release_sha256 != selected.successor.release_sha256:
            _invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
        return retry_pointer
    candidate = _authenticate_native_staged_candidate(runtime.run_dir, native_staged)
    parent, _parent_manifest = load_bamf_generation_authority(
        runtime.run_dir / "bamf-state.json")
    accepted_current = read_accepted_atlas_factory_release(runtime.run_dir)
    accepted_current.verify_semantic_catalog(runtime.graph)
    current_program = schedule_program_from_executable_release(accepted_current)
    school = runtime_state._state_from_json(runtime.receipt["school"], current_program)
    if (accepted_current.release_sha256 != current.release_sha256
            or school.current_student != checkpoint):
        _invalid("BAMF_ATLAS_RUNTIME_CONTEXT_CHANGED")
    require_staged_vocabulary_admission_headroom(
        runtime.run_dir, native_staged)
    release_file = runtime_admission._persist_executable_factory_release(
        runtime.run_dir, selected.successor)
    expected_release_file = (
        "factory-releases/" + selected.successor.release_sha256 + ".json")
    if release_file != expected_release_file:
        _invalid("BAMF_ATLAS_FACTORY_RELEASE_DURABLE_DRIFT")
    binding = _issue_atlas_admission_binding(
        candidate, parent,
        lease_sha256=atlas_lease.digest(),
        source_approval_sha256=contract_digest(atlas_lease.source_approval),
        proposal_sha256=proposal.proposal_sha256,
        factory_release_sha256=selected.successor.release_sha256,
        staging_receipt_sha256=staging_digest,
        parent_feature_receipt_sha256=parent_feature,
    )
    pointer = publish_atlas_admission_generation(
        runtime.run_dir, candidate, admission=binding,
        reserve_gib=float(runtime.reserve_gib))
    accepted_release = read_accepted_atlas_factory_release(runtime.run_dir)
    if accepted_release.release_sha256 != selected.successor.release_sha256:
        _invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
    return pointer
