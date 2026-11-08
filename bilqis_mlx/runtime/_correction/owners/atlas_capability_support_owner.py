"""Production C09 ownership for learned capability support from accepted B13 custody."""
from __future__ import annotations

from pathlib import Path
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex,
)

from .atlas_requalification_contracts import (
    CapabilitySupport, RequalificationLedger, RequalificationStatus,
    RequalificationUpdate,
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
    event_from_record, journal_path, read_journal, write_journal,
)
from .capability_support_loading import load_current_support
from .capability_support_requalification import (
    install_requalification, rehydrate_support_hold,
)


_ISSUER = object()


class CapabilitySupportArtifactOwner:
    """Stateful before-read hold owner for one source-qualified learned capability."""

    _context_revalidation_materializes_metadata = True

    def __init__(self, *args, **kwargs):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or not isinstance(self._ledger, RequalificationLedger)
                or len(self._ledger.capabilities) != 1
                or not isinstance(self._capability_id, str)
                or self._ledger.capabilities[0].capability_id != self._capability_id
                or not isinstance(self._index, DependencyIndex)
                or not isinstance(self._generation_bindings, tuple)
                or len(self._generation_bindings) != 1
                or any(not _digest(item) for item in self._generation_bindings)
                or self._index.node(self.support.support_artifact_ids[0]).kind
                is not ArtifactKind.CAPABILITY_SUPPORT):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_INVALID")

    @property
    def capability_id(self) -> str:
        return self._capability_id

    @property
    def support(self) -> CapabilitySupport:
        return self._ledger.capability(self.capability_id)

    @property
    def ledger(self) -> RequalificationLedger:
        return self._ledger

    @property
    def current_node(self) -> ArtifactNode:
        return self._index.node(self.support.support_artifact_ids[0])

    @property
    def index(self) -> DependencyIndex:
        return self._index

    def _install_context_revalidation(
        self, index: DependencyIndex, transition,
    ) -> bool:
        if (not isinstance(index, DependencyIndex)
                or {node.artifact_id for node in index.nodes}
                != {node.artifact_id for node in self._index.nodes}):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_INDEX_DRIFT")
        self._index = index
        if transition.changed:
            from bilqis_mlx.runtime.atlas_requalification import (
                mark_context_affected_capability,
            )
            self.install_requalification(
                mark_context_affected_capability(self.ledger, transition))
        return True

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
        if self.support.status is not RequalificationStatus.QUALIFIED:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_REQUIRED")
        if self._queue is not None:
            read_artifact(self._index, self._queue, self.current_node.artifact_id)
        elif not self.current_node.eligible:
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        return self.support

    def install_requalification(self, update: RequalificationUpdate) -> None:
        """Install this capability's slice of one durable aggregate update."""
        install_requalification(self, update)

    def apply_correction(
        self, event: CorrectionEvent, authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationQueue:
        from bilqis_mlx.runtime.accepted_correction_runtime import (
            require_bound_owner_registry,
        )
        authority_registry = require_bound_owner_registry(self, authority_registry)
        self._queue = apply_correction(event, self._index, authority_registry)
        if self._journal_path is not None and self._queue.held_artifact_ids:
            write_journal(
                self._journal_path,
                capability_id=self.capability_id,
                manifest_sha256=self._accepted_manifest_sha256,
                artifact_id=self.current_node.artifact_id,
                state="HELD", event=event, ledger=self.ledger)
        return self._queue

    def advance(
        self, frontier: RevalidationFrontier,
        authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationProgress:
        from bilqis_mlx.runtime.accepted_correction_runtime import (
            require_bound_owner_registry,
        )
        authority_registry = require_bound_owner_registry(self, authority_registry)
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
            from bilqis_mlx.runtime.atlas_requalification import (
                mark_affected_capabilities,
            )
            self.install_requalification(mark_affected_capabilities(
                self.ledger, self._index, self._queue))
            if self._journal_path is not None:
                write_journal(
                    self._journal_path,
                    capability_id=self.capability_id,
                    manifest_sha256=self._accepted_manifest_sha256,
                    artifact_id=self.current_node.artifact_id,
                    state="REQUALIFICATION_REQUIRED", event=self._queue.event,
                    transition=transition, ledger=self.ledger)
        elif (self._journal_path is not None
              and not self._queue.held_artifact_ids and not self._queue.pending):
            write_journal(
                self._journal_path,
                capability_id=self.capability_id,
                manifest_sha256=self._accepted_manifest_sha256,
                artifact_id=self.current_node.artifact_id,
                state="CLEARED", event=self._queue.event,
                transition=transition, ledger=self.ledger)
        return progress


def _issue_owner(
    support, node, generation_bindings=(), journal=None,
    accepted_manifest_sha256=None,
):
    owner = object.__new__(CapabilitySupportArtifactOwner)
    owner._capability_id = support.capability_id
    owner._ledger = RequalificationLedger((support,))
    owner._index = DependencyIndex.build((node,))
    owner._queue = None
    owner._generation_bindings = tuple(generation_bindings)
    owner._journal_path = journal
    owner._accepted_manifest_sha256 = (
        support.retained_generation_sha256
        if accepted_manifest_sha256 is None else accepted_manifest_sha256)
    owner._issuance = _ISSUER
    owner.__post_init__()
    return owner


def load_capability_support_owner(
    run_dir: Path, capability_id: str,
) -> CapabilitySupportArtifactOwner:
    """Materialize current support only from accepted B13 lossless source anchors."""
    run_dir = Path(run_dir)
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        _accepted_correction_registry,
    )
    manifest_sha256, support, node, generation_bindings = load_current_support(
        run_dir, capability_id)
    cache, authority_registry = _accepted_correction_registry(run_dir)
    if cache.accepted_manifest_sha256 != manifest_sha256:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTED_GENERATION_DRIFT")
    hold_path = journal_path(run_dir, manifest_sha256, capability_id)
    owner = _issue_owner(
        support, node, generation_bindings, hold_path,
        accepted_manifest_sha256=manifest_sha256)
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
        rehydrated = rehydrate_support_hold(
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
    from ._atlas_owner_ingress import _route
    register_accepted_target(
        run_dir, manifest_sha256, "CAPABILITY_SUPPORT", rehydrated,
        lambda current, event, registry: _route(current, event, registry),
        seen_event_ids=seen_event_ids,
    )
    return rehydrated


__all__ = ("CapabilitySupportArtifactOwner", "load_capability_support_owner")
