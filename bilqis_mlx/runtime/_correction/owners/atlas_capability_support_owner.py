"""Production C09 ownership for learned capability support from accepted B13 custody."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    ACCEPTANCE_SCHEMA, AcceptedCandidateBinding, candidate_identity_digest,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex,
)

from .atlas_requalification_contracts import (
    CapabilitySupport, RequalificationLedger, RequalificationStatus,
)
from .atlas_revalidation_common import _digest, _invalid
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_revalidation_queue import RevalidationProgress, RevalidationQueue
from .atlas_revalidation_runtime import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from .atlas_source_authority import SourceAuthorityRegistry
from .capability_support_journal import (
    event_from_record, journal_path, read_journal, transition_from_record,
    write_journal,
)
from .capability_support_materialization import materialized_support


_ISSUER = object()


class CapabilitySupportArtifactOwner:
    """Stateful before-read hold owner for one source-qualified learned capability."""

    def __init__(self, *args, **kwargs):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or not isinstance(self._support, CapabilitySupport)
                or not isinstance(self._index, DependencyIndex)
                or not isinstance(self._generation_bindings, tuple)
                or len(self._generation_bindings) != 1
                or any(not _digest(item) for item in self._generation_bindings)
                or self._index.node(self._support.support_artifact_ids[0]).kind
                is not ArtifactKind.CAPABILITY_SUPPORT):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_INVALID")

    @property
    def capability_id(self) -> str:
        return self._support.capability_id

    @property
    def support(self) -> CapabilitySupport:
        return self._support

    @property
    def ledger(self) -> RequalificationLedger:
        return RequalificationLedger((self._support,))

    @property
    def current_node(self) -> ArtifactNode:
        return self._index.node(self._support.support_artifact_ids[0])

    @property
    def index(self) -> DependencyIndex:
        return self._index

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    def require(
        self, capability_id: str, generation_binding: str | None = None,
    ) -> CapabilitySupport:
        if capability_id != self.capability_id:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_MISMATCH")
        if (generation_binding is not None
                and generation_binding not in self._generation_bindings):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_GENERATION_DRIFT")
        from bilqis_mlx.runtime.accepted_correction_runtime import require_pending_corrections
        require_pending_corrections(self, self.current_node.artifact_id)
        if self._support.status is not RequalificationStatus.QUALIFIED:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_REQUIRED")
        if self._queue is not None:
            read_artifact(self._index, self._queue, self.current_node.artifact_id)
        elif not self.current_node.eligible:
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        return self._support

    def apply_correction(
        self, event: CorrectionEvent, authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationQueue:
        self._queue = apply_correction(event, self._index, authority_registry)
        if self._journal_path is not None and self._queue.held_artifact_ids:
            write_journal(
                self._journal_path,
                capability_id=self.capability_id,
                manifest_sha256=self._support.retained_generation_sha256,
                artifact_id=self.current_node.artifact_id,
                state="HELD", event=event)
        return self._queue

    def advance(
        self, frontier: RevalidationFrontier,
        authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationProgress:
        if self._queue is None:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_REVALIDATION_NOT_HELD")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_REVALIDATION_NOT_PENDING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        if transition.changed:
            self._support = replace(
                self._support,
                status=RequalificationStatus.REQUALIFICATION_REQUIRED)
            if self._journal_path is not None:
                write_journal(
                    self._journal_path,
                    capability_id=self.capability_id,
                    manifest_sha256=self._support.retained_generation_sha256,
                    artifact_id=self.current_node.artifact_id,
                    state="REQUALIFICATION_REQUIRED", event=self._queue.event,
                    transition=transition)
        elif (self._journal_path is not None
              and not self._queue.held_artifact_ids and not self._queue.pending):
            write_journal(
                self._journal_path,
                capability_id=self.capability_id,
                manifest_sha256=self._support.retained_generation_sha256,
                artifact_id=self.current_node.artifact_id,
                state="CLEARED", event=self._queue.event,
                transition=transition)
        return progress


def _issue_owner(support, node, generation_bindings=(), journal=None):
    owner = object.__new__(CapabilitySupportArtifactOwner)
    owner._support = support
    owner._index = DependencyIndex.build((node,))
    owner._queue = None
    owner._generation_bindings = tuple(generation_bindings)
    owner._journal_path = journal
    owner._issuance = _ISSUER
    owner.__post_init__()
    return owner


def _load_accepted_support(run_dir: Path, capability_id: str):
    from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle
    from bilqis_mlx.runtime.bamf_bundle.publication import (
        ACCEPTANCE_DIR, _live_bundle_manifest, _pointer_lock, _read_pointer,
    )

    with _pointer_lock(run_dir):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        if pointer is None:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_GENERATION_MISSING")
        manifest_sha256 = pointer["manifest_sha256"]
        _live_bundle_manifest(run_dir, pointer)
        student = load_bamf_bundle(
            run_dir / "bamf-bundles" / manifest_sha256,
            expected_manifest_sha256=manifest_sha256)
        path = run_dir / ACCEPTANCE_DIR / f"{manifest_sha256}.json"
        if path.is_symlink() or not path.is_file():
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_MISSING")
        try:
            binding = AcceptedCandidateBinding.from_record(json.loads(path.read_bytes()))
        except (UnicodeDecodeError, json.JSONDecodeError, BilqisError):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_INVALID")
        if (binding.schema_version != ACCEPTANCE_SCHEMA
                or binding.digest != pointer.get("acceptance_sha256")
                or binding.run_id != student.run_id
                or binding.generation != student.generation
                or binding.feature_sha256 != student.extents.factor_map_digest
                or binding.optimizer_step != student.retained_state.optimizer_step
                or binding.candidate_identity_sha256
                != candidate_identity_digest(student.retained_state)
                or binding.step_proof_sha256 != tuple(
                    proof.digest for proof in student.retained_state.step_proofs)):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_DRIFT")
    support, node, generation_bindings = materialized_support(
        binding, student, manifest_sha256, capability_id)
    return manifest_sha256, support, node, generation_bindings


def _rehydrate_support_hold(
    owner, hold, node, authority_registry: SourceAuthorityRegistry | None,
):
    if hold is None:
        return owner
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_CORRECTION_AUTHORITY_REQUIRED")
    event = event_from_record(hold.get("event"))
    authority_registry.verify_correction(event)
    transition = transition_from_record(hold.get("transition"))
    if transition is not None:
        authority_registry.verify_transition(transition)
        if (transition.artifact_id != node.artifact_id
                or transition.correction_event_id != event.event_id
                or transition.correction_receipt_sha256
                != event.source_receipt_sha256
                or transition.previous_content_digest != node.content_digest
                or transition.previous_eligible != node.eligible
                or transition.immediate_dependencies
                != node.immediate_dependencies):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
    if hold["state"] == "CLEARED":
        if transition is None or transition.changed:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
        return owner
    if hold["state"] == "REQUALIFICATION_REQUIRED":
        if transition is None or not transition.changed:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
        owner._support = replace(
            owner._support,
            status=RequalificationStatus.REQUALIFICATION_REQUIRED)
        return owner
    if transition is not None:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
    owner._queue = apply_correction(event, owner._index, authority_registry)
    return owner


def load_capability_support_owner(
    run_dir: Path, capability_id: str,
    authority_registry: SourceAuthorityRegistry | None = None,
) -> CapabilitySupportArtifactOwner:
    """Materialize current support only from accepted B13 custody and v3 source anchors."""
    run_dir = Path(run_dir)
    manifest_sha256, support, node, generation_bindings = _load_accepted_support(
        run_dir, capability_id)
    hold_path = journal_path(run_dir, manifest_sha256, capability_id)
    owner = _issue_owner(support, node, generation_bindings, hold_path)
    hold = read_journal(
        hold_path,
        capability_id=capability_id,
        manifest_sha256=manifest_sha256,
        artifact_id=node.artifact_id,
    )
    if hold is None:
        rehydrated = owner
        seen_event_ids = ()
    else:
        if (hold.get("capability_id") != capability_id
                or hold.get("manifest_sha256") != manifest_sha256
                or hold.get("artifact_id") != node.artifact_id
                or hold.get("state") not in {
                    "HELD", "CLEARED", "REQUALIFICATION_REQUIRED"}):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
        rehydrated = _rehydrate_support_hold(
            owner, hold, node, authority_registry)
        from bilqis_mlx.runtime.accepted_corrections import (
            accepted_correction_id,
        )
        seen_event_ids = (
            accepted_correction_id(
                manifest_sha256, event_from_record(hold.get("event"))),
        )
    from bilqis_mlx.runtime.accepted_corrections import (
        register_accepted_target,
    )
    from .atlas_owner_ingress import apply_capability_support_correction
    register_accepted_target(
        run_dir, manifest_sha256, "CAPABILITY_SUPPORT", rehydrated,
        lambda event, registry: apply_capability_support_correction(
            rehydrated, event, registry),
        authority_registry,
        seen_event_ids=seen_event_ids,
    )
    return rehydrated


__all__ = ("CapabilitySupportArtifactOwner", "load_capability_support_owner")
