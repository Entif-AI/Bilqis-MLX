"""Read-only adapter from the canonical Akasha factory ledger into CP02."""
from __future__ import annotations

from dataclasses import dataclass
import json
from types import MappingProxyType

from bilqis_mlx.runtime.akasha_factory_ledger import (
    FactoryLedgerProjection, FactoryLifecycleState, TopologyKnowledge,
)

from .contracts.factory import (
    FactoryAdmissionAuthority, FactoryBlocker, FactoryCockpitSnapshot,
    FactoryCurrencyState, FactoryDeliveryStatus, FactoryGradeFrontier, FactoryLifecycleStatus,
    FactoryRunLineage, FactorySubjectKind, FactoryTopologyEvidence,
    FactoryTopologyKnowledge,
)
from .contracts.model import AuthorityClass, CoverageState, RecordMeta, is_sha256, require


_LIFECYCLE = MappingProxyType({
    FactoryLifecycleState.CURRICULUM_CANDIDATE: FactoryLifecycleStatus.CURRICULUM_CANDIDATE,
    FactoryLifecycleState.FACTORY_VALIDATED: FactoryLifecycleStatus.FACTORY_VALIDATED,
    FactoryLifecycleState.QUALIFIED: FactoryLifecycleStatus.QUALIFIED,
    FactoryLifecycleState.STAGED: FactoryLifecycleStatus.STAGED,
    FactoryLifecycleState.ADMITTED: FactoryLifecycleStatus.ADMITTED,
    FactoryLifecycleState.PROMOTED: FactoryLifecycleStatus.PROMOTED,
    FactoryLifecycleState.DEBT: FactoryLifecycleStatus.DEBT,
    FactoryLifecycleState.SUPERSEDED: FactoryLifecycleStatus.SUPERSEDED,
})


@dataclass(frozen=True)
class FactoryCockpitOverlay:
    """Optional independently-evidenced product posture layered onto ledger truth."""

    subject_sha256: str
    delivery_status: FactoryDeliveryStatus = FactoryDeliveryStatus.NOT_EVIDENCED
    blockers: tuple[FactoryBlocker, ...] = ()
    qualification_receipt_sha256: str | None = None
    admission_receipt_sha256: str | None = None

    def __post_init__(self) -> None:
        require(is_sha256(self.subject_sha256), "FACTORY_OVERLAY_SUBJECT")
        require(type(self.delivery_status) is FactoryDeliveryStatus,
                "FACTORY_OVERLAY_DELIVERY")
        require(type(self.blockers) is tuple
                and all(type(item) is FactoryBlocker for item in self.blockers),
                "FACTORY_OVERLAY_BLOCKERS")
        require((self.delivery_status is FactoryDeliveryStatus.BLOCKED) == bool(self.blockers),
                "FACTORY_OVERLAY_BLOCKER_STATUS")
        require(self.qualification_receipt_sha256 is None
                or is_sha256(self.qualification_receipt_sha256),
                "FACTORY_OVERLAY_QUALIFICATION")
        require(self.admission_receipt_sha256 is None
                or is_sha256(self.admission_receipt_sha256),
                "FACTORY_OVERLAY_ADMISSION")


def _topology(value) -> FactoryTopologyEvidence:
    if value.knowledge is TopologyKnowledge.EXACT:
        return FactoryTopologyEvidence(
            FactoryTopologyKnowledge.EXACT,
            value.schema_version,
            value.topology_schema,
            value.topology_digest,
            value.architecture_id,
            value.layers,
            value.query_heads,
            value.kv_heads,
            value.model_dimension,
            value.feed_forward_dimension,
            value.context_length,
            None,
        )
    return FactoryTopologyEvidence(
        FactoryTopologyKnowledge.HISTORICAL_COMPATIBILITY_REQUIRED,
        value.schema_version,
        None, None, None, None, None, None, None, None, None,
        value.compatibility_ref,
    )


def _lineage(checkpoints) -> tuple[FactoryRunLineage, ...]:
    return tuple(FactoryRunLineage(
        run_id=item.run_id,
        checkpoint_lineage_id=item.checkpoint_lineage_id,
        generation=None,
        generation_manifest_sha256=item.generation_manifest_sha256,
        checkpoint_sha256=item.checkpoint_sha256,
        checkpoint_receipt_sha256=item.checkpoint_receipt_sha256,
        topology=_topology(item.topology),
    ) for item in checkpoints)


def _grade_frontier(release) -> tuple[FactoryGradeFrontier, ...]:
    manifest = json.loads(release.manifest_json)
    return tuple(FactoryGradeFrontier(
        item["grade_id"], tuple(item["capabilities"]),
    ) for item in manifest.get("grades", ()))


def _latest(events) -> FactoryLifecycleStatus:
    if not events:
        return FactoryLifecycleStatus.UNKNOWN
    return _LIFECYCLE[events[-1].state]


def _currency(subject, lifecycle, current_factory_release_sha256):
    if current_factory_release_sha256 is None:
        return (FactoryCurrencyState.STALE
                if lifecycle is FactoryLifecycleStatus.SUPERSEDED
                else FactoryCurrencyState.UNKNOWN)
    if subject == current_factory_release_sha256:
        return FactoryCurrencyState.CURRENT
    return FactoryCurrencyState.STALE


def _meta(record_id, projection, materialized_at, *, evidence_refs=(), receipt_refs=()):
    return RecordMeta(
        record_id=record_id,
        run=None,
        materialized_at=materialized_at,
        observed_at=None,
        as_of=None,
        coverage=CoverageState.COMPLETE,
        authority=AuthorityClass.DERIVED,
        source_refs=(f"akasha-factory-ledger:{projection.identity.projection_sha256}",),
        evidence_refs=tuple(evidence_refs),
        receipt_refs=tuple(receipt_refs),
    )


def _overlay_map(overlays):
    values = tuple(overlays)
    require(all(type(item) is FactoryCockpitOverlay for item in values),
            "FACTORY_OVERLAYS")
    mapped = {item.subject_sha256: item for item in values}
    require(len(mapped) == len(values), "FACTORY_OVERLAY_DUPLICATE")
    return mapped


def _evidence_refs(overlay):
    return tuple(sorted({
        ref for blocker in overlay.blockers
        for ref in (blocker.owner_ref, blocker.evidence_ref)
    }))


def _release_snapshot(
    release, projection, materialized_at, current_factory_release_sha256, overlay_map,
):
    subject = release.factory_release_sha256
    direct = tuple(item for item in projection.lifecycle
                   if item.factory_release_sha256 == subject)
    lifecycle = _latest(direct)
    overlay = overlay_map.get(subject, FactoryCockpitOverlay(subject))
    receipts = tuple(sorted({
        release.artifact_receipt_sha256,
        *(item.receipt_sha256 for item in direct),
        *(item.checkpoint_receipt_sha256 for item in projection.checkpoints
          if item.factory_release_sha256 == subject),
        *(value for value in (
            overlay.qualification_receipt_sha256,
            overlay.admission_receipt_sha256,
        ) if value is not None),
    }))
    promoted = tuple(sorted({item.capability_id for item in direct
                             if item.state is FactoryLifecycleState.PROMOTED
                             and item.capability_id is not None}))
    debt = tuple(sorted({item.capability_id for item in direct
                         if item.state is FactoryLifecycleState.DEBT
                         and item.capability_id is not None}))
    return FactoryCockpitSnapshot(
        _meta(
            f"factory-release:{subject}", projection, materialized_at,
            evidence_refs=_evidence_refs(overlay),
            receipt_refs=receipts,
        ),
        FactorySubjectKind.FACTORY_RELEASE,
        subject,
        subject,
        None,
        release.semantic_release_sha256,
        lifecycle,
        overlay.delivery_status,
        _currency(subject, lifecycle, current_factory_release_sha256),
        FactoryAdmissionAuthority.HUMAN_ONLY,
        _grade_frontier(release),
        release.capability_ids,
        release.dependency_edges,
        overlay.blockers,
        promoted,
        debt,
        receipts,
        overlay.qualification_receipt_sha256,
        overlay.admission_receipt_sha256,
        _lineage(tuple(item for item in projection.checkpoints
                       if item.factory_release_sha256 == subject)),
    )


def _candidate_snapshot(
    candidate, projection, materialized_at, current_factory_release_sha256, overlay_map,
):
    subject = candidate.candidate_sha256
    direct = tuple(item for item in projection.lifecycle
                   if item.candidate_sha256 == subject)
    lifecycle = _latest(direct)
    overlay = overlay_map.get(subject, FactoryCockpitOverlay(subject))
    resulting_release = next((
        item.factory_release_sha256 for item in reversed(direct)
        if item.factory_release_sha256 is not None
    ), None)
    receipts = tuple(sorted({
        candidate.artifact_receipt_sha256,
        *(item.receipt_sha256 for item in direct),
        *(value for value in (
            overlay.qualification_receipt_sha256,
            overlay.admission_receipt_sha256,
        ) if value is not None),
    }))
    return FactoryCockpitSnapshot(
        _meta(
            f"factory-candidate:{subject}", projection, materialized_at,
            evidence_refs=_evidence_refs(overlay),
            receipt_refs=receipts,
        ),
        FactorySubjectKind.CURRICULUM_CANDIDATE,
        subject,
        resulting_release,
        subject,
        candidate.semantic_release_sha256,
        lifecycle,
        overlay.delivery_status,
        (FactoryCurrencyState.CURRENT
         if resulting_release == current_factory_release_sha256
         else FactoryCurrencyState.UNKNOWN),
        FactoryAdmissionAuthority.HUMAN_ONLY,
        (),
        candidate.capability_ids,
        candidate.dependency_edges,
        overlay.blockers,
        (),
        (),
        receipts,
        overlay.qualification_receipt_sha256,
        overlay.admission_receipt_sha256,
        _lineage(tuple(item for item in projection.checkpoints
                       if item.factory_release_sha256 == resulting_release)),
    )


def project_factory_cockpit(
    projection: FactoryLedgerProjection,
    *,
    materialized_at: int,
    current_factory_release_sha256: str | None = None,
    overlays: tuple[FactoryCockpitOverlay, ...] = (),
) -> tuple[FactoryCockpitSnapshot, ...]:
    """Project an already-authorized Akasha ledger without acquiring write authority."""
    require(type(projection) is FactoryLedgerProjection, "FACTORY_LEDGER_PROJECTION_REQUIRED")
    require(type(materialized_at) is int and 0 <= materialized_at <= (1 << 53) - 1,
            "FACTORY_MATERIALIZED_AT")
    require(current_factory_release_sha256 is None
            or is_sha256(current_factory_release_sha256), "FACTORY_CURRENT_RELEASE")
    overlay_map = _overlay_map(overlays)
    records = [
        *(_release_snapshot(
            release, projection, materialized_at,
            current_factory_release_sha256, overlay_map,
        ) for release in projection.releases),
        *(_candidate_snapshot(
            candidate, projection, materialized_at,
            current_factory_release_sha256, overlay_map,
        ) for candidate in projection.candidates),
    ]

    return tuple(sorted(records, key=lambda item: (
        item.subject_kind.value, item.subject_sha256)))


__all__ = ("FactoryCockpitOverlay", "project_factory_cockpit")
