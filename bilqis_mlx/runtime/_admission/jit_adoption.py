"""Revalidate and commit a selected JIT proposal through the native transaction.

The public C07 policy owns lease/source scope. This owner removes the old executor
gap after those checks have succeeded: its native path independently replays the
persisted lease and accepted B13 parent, then publishes the exact A02-staged
candidate. A provisional ``DISPOSABLE_CONTRACT`` value by itself is never authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ..factory.jit_curriculum import ProposalDisposition, propose_curriculum_delta
from .atlas_lease_contracts import LeaseRunIdentity, _invalid, _sha


def _accepted_lease_run_identity(run_identity) -> LeaseRunIdentity:
    """Project accepted B13 birth identity into the lease's frozen identity shape.

    The projection is a comparison value only.  It does not turn the
    ``DISPOSABLE_CONTRACT`` record into B13 authority; the accepted run remains
    authoritative and must be reloaded independently before mutation.
    """
    from bilqis_mlx.learning.champions import Checkpoint
    from bilqis_mlx.runtime.bamf_bundle.genesis import BamfRunIdentity

    if type(run_identity) is not BamfRunIdentity:
        _invalid("BAMF_ATLAS_ACCEPTED_RUN_IDENTITY_REQUIRED")
    return LeaseRunIdentity(
        run_identity.run_id,
        run_identity.initial_candidate_identity_sha256,
        run_identity.initial_topology_digest,
        Checkpoint(
            run_identity.origin_checkpoint_sha256,
            run_identity.origin_checkpoint_filename,
            run_identity.origin_optimizer_step,
            True,
        ),
    )


def resolve_ready_candidate(frontier, current, ledger, plan, checkpoint, proposal, staged):
    proposal.verify()
    if proposal.disposition is not ProposalDisposition.PROPOSAL:
        raise ValueError("JIT_ADOPTION_READY_PROPOSAL_REQUIRED")
    for item in staged:
        item.verify(frontier, current)
    fresh = propose_curriculum_delta(frontier, current, ledger, plan,
        checkpoint.sha256, checkpoint.optimizer_step,
        candidate_bindings=tuple(item.binding for item in staged))
    if fresh != proposal:
        raise ValueError("JIT_ADOPTION_PROPOSAL_CONTEXT_CHANGED")
    matches = tuple(item for item in staged if
        (item.candidate_id,) == proposal.selected_candidate_ids and
        item.successor.release_sha256 == proposal.selected_successor_sha256)
    if len(matches) != 1:
        raise ValueError("JIT_ADOPTION_EXACT_SUCCESSOR_REQUIRED")
    return matches[0]


def verify_current_implementations(successor, source_registry, answer_registry):
    """A sealed historical package cannot authorize changed provider code."""
    sources = {item.adapter_id: item for item in successor.source_adapters}
    for execution in successor.execution_plan.capabilities:
        binding = successor.source_bindings.by_capability[execution.capability_id]
        actual = source_registry.require(binding.generator_id, binding.oracle_id).descriptor
        if actual != sources.get(execution.provider_id):
            raise ValueError("JIT_ADOPTION_SOURCE_IMPLEMENTATION_DRIFT")
    if tuple(answer_registry.require(item.kind).descriptor
             for item in successor.answer_modalities) != successor.answer_modalities:
        raise ValueError("JIT_ADOPTION_ANSWER_IMPLEMENTATION_DRIFT")


def _authenticate_native_staged_candidate(
        run_dir: Path, candidate, *, expected_candidate_identity_sha256: str,
        expected_parent_feature_receipt_sha256: str):
    """Bind one opaque A02-staged candidate to the live accepted B13 parent.

    The two supplied digests are only cross-owner anchors. They grant no
    admission or publication authority by themselves; the future A02 adapter
    must first verify its own typed staging receipt before calling this helper.
    """
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.runtime.bamf_bundle import (
        BamfBundleCandidate, load_bamf_generation_authority,
        read_accepted_generation_feature_receipt,
    )

    if (not isinstance(run_dir, Path) or type(candidate) is not BamfBundleCandidate
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
    from dataclasses import fields
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
        accepted_binding_for_manifest, accepted_generation,
    )
    from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
        ParsedAtlasAdmissionBinding,
    )
    from bilqis_mlx.runtime.bamf_bundle.records import BamfBundleCandidate
    from bilqis_mlx.semantics.domains import contract_digest

    pointer, accepted = accepted_generation(run_dir / "bamf-state.json")
    if accepted.generation < candidate.generation:
        return None
    if accepted.generation != candidate.generation:
        _invalid("BAMF_ATLAS_NATIVE_RETRY_DRIFT")
    if (type(candidate) is not BamfBundleCandidate
            or any(getattr(accepted, item.name) != getattr(candidate, item.name)
                   for item in fields(BamfBundleCandidate))
            or candidate_identity_digest(accepted.retained_state) != candidate_identity):
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


@dataclass(frozen=True)
class _PreparedSuccessorRuntime:
    """The one mutable learner lane as immutable executor inputs.

    Constructing this record grants no admission authority.  Every execution
    re-reads the admitted Factory release and school checkpoint from ``receipt``
    immediately before entering the existing prepared-successor transaction.
    """

    mx: object
    run_dir: Path
    receipt: dict
    grade_a_course: object
    source_root: Path | None
    graph: dict
    parameters: object
    optimizer: object
    reserve_gib: float
    native_pointer: dict | None = None

    def __post_init__(self):
        if (not isinstance(self.run_dir, Path) or not isinstance(self.receipt, dict)
                or not isinstance(self.graph, dict)
                or not isinstance(self.reserve_gib, (int, float))
                or self.reserve_gib < 0
                or (self.native_pointer is not None
                    and not isinstance(self.native_pointer, dict))):
            _invalid("BAMF_ATLAS_EXECUTOR_CONTEXT_INVALID")


def _publish_native_staged_candidate(
        runtime, selected, proposal, native_staged, atlas_lease,
        source_authority):
    """Publish the exact A02 state after C07 and B13 authority replay."""
    from . import admission as runtime_admission
    from bilqis_mlx.runtime.atlas_admission import (
        read_accepted_atlas_factory_release, read_accepted_atlas_lease,
    )
    from bilqis_mlx.runtime.bamf_bundle import (
        load_bamf_generation_authority, publish_atlas_admission_generation,
    )
    from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
        _issue_atlas_admission_binding,
    )
    from bilqis_mlx.semantics.domains import contract_digest

    candidate = getattr(native_staged, "candidate", None)
    staging_receipt = getattr(native_staged, "receipt", None)
    candidate_identity = getattr(
        staging_receipt, "candidate_identity_sha256", None)
    parent_feature = getattr(
        staging_receipt, "parent_feature_receipt_sha256", None)
    staging_digest = getattr(staging_receipt, "digest", None)
    if (candidate is None or staging_receipt is None
            or not _sha(candidate_identity) or not _sha(parent_feature)
            or not _sha(staging_digest)):
        _invalid("BAMF_ATLAS_NATIVE_STAGING_ARGUMENT_INVALID")

    persisted = read_accepted_atlas_lease(
        runtime.run_dir, source_authority=source_authority)
    if persisted is None or persisted != atlas_lease:
        _invalid("BAMF_ATLAS_PERSISTED_LEASE_REQUIRED")
    release_file = runtime_admission._persist_executable_factory_release(
        runtime.run_dir, selected.successor)
    expected_release_file = (
        "factory-releases/" + selected.successor.release_sha256 + ".json")
    if release_file != expected_release_file:
        _invalid("BAMF_ATLAS_FACTORY_RELEASE_DURABLE_DRIFT")
    retry_pointer = _accepted_native_retry(
        runtime.run_dir, candidate, candidate_identity=candidate_identity,
        parent_feature=parent_feature, staging_digest=staging_digest,
        atlas_lease=atlas_lease, proposal=proposal, selected=selected)
    if retry_pointer is not None:
        accepted_release = read_accepted_atlas_factory_release(runtime.run_dir)
        if accepted_release.release_sha256 != selected.successor.release_sha256:
            _invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
        return retry_pointer
    candidate = _authenticate_native_staged_candidate(
        runtime.run_dir, candidate,
        expected_candidate_identity_sha256=candidate_identity,
        expected_parent_feature_receipt_sha256=parent_feature)
    parent, _parent_manifest = load_bamf_generation_authority(
        runtime.run_dir / "bamf-state.json")
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


def _execute_prepared_successor_adoption(
        runtime: _PreparedSuccessorRuntime, *, frontier, current, ledger, plan,
        checkpoint, proposal, staged, source_registry, answer_registry,
        native_staged=None, atlas_lease=None, source_authority=None):
    """Freshly revalidate then enter the existing atomic prepared-successor owner.

    This is deliberately a concrete owner, not a caller callback.  It cannot
    create a lease, reinterpret a source approval, or claim that a disposable
    C07 contract is production run authority.
    """
    if not isinstance(runtime, _PreparedSuccessorRuntime):
        _invalid("BAMF_ATLAS_EXECUTOR_RUNTIME_INVALID")
    selected = resolve_ready_candidate(
        frontier, current, ledger, plan, checkpoint, proposal, staged)
    verify_current_implementations(
        selected.successor, source_registry, answer_registry)

    from . import admission as runtime_admission
    from . import release_adoption, state as runtime_state
    from ..factory.schedule import schedule_program_from_executable_release

    admitted = runtime_admission._require_executable_factory_admission(
        runtime.run_dir, runtime.receipt, runtime.graph)
    program = schedule_program_from_executable_release(admitted)
    school = runtime_state._state_from_json(runtime.receipt["school"], program)
    if (admitted.release_sha256 != current.release_sha256
            or school.current_student != checkpoint):
        _invalid("BAMF_ATLAS_RUNTIME_CONTEXT_CHANGED")

    native_inputs = (native_staged, atlas_lease, source_authority)
    if any(value is not None for value in native_inputs):
        if any(value is None for value in native_inputs):
            _invalid("BAMF_ATLAS_NATIVE_ADOPTION_ARGUMENT_INVALID")
        pointer = _publish_native_staged_candidate(
            runtime, selected, proposal, native_staged, atlas_lease,
            source_authority)
        return replace(runtime, native_pointer=pointer)

    parameters, optimizer, graph, receipt, course = (
        release_adoption._adopt_prepared_successor(
            runtime.mx, runtime.run_dir, runtime.receipt,
            runtime.grade_a_course, runtime.source_root, runtime.graph,
            runtime.parameters, runtime.optimizer, selected,
            reserve_gib=float(runtime.reserve_gib)))
    return replace(
        runtime, receipt=receipt, grade_a_course=course, graph=graph,
        parameters=parameters, optimizer=optimizer)
