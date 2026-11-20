"""Read-only Factory cockpit projection from authenticated accepted BAMF history."""
from __future__ import annotations

from collections import defaultdict

from bilqis_mlx.mission_control.contracts.factory import (
    FactoryAdmissionAuthority, FactoryCockpitSnapshot, FactoryCurrencyState,
    FactoryDeliveryStatus, FactoryLifecycleStatus, FactoryRunLineage,
    FactorySubjectKind, FactoryTopologyEvidence, FactoryTopologyKnowledge,
)
from bilqis_mlx.mission_control.contracts.model import (
    AuthorityClass, CoverageState, RecordMeta,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

from .native_contracts import AuthenticatedGeneration, invalid, run_ref


_TOPOLOGY_VIEW_SCHEMA = "bilqis.akasha.factory-topology-view/v1"
_ADOPTION_EVENT = "BAMF_FACTORY_RELEASE_ADOPTION_COMMITTED"


def _topology(generation: AuthenticatedGeneration) -> FactoryTopologyEvidence:
    record = generation.manifest.get("topology")
    try:
        topology = ModelTopologySpecV2.from_record(record)
    except (TypeError, ValueError):
        invalid("CONTROL_PLANE_FACTORY_TOPOLOGY_INVALID")
    return FactoryTopologyEvidence(
        knowledge=FactoryTopologyKnowledge.EXACT,
        view_schema_version=_TOPOLOGY_VIEW_SCHEMA,
        topology_schema=record["schema"],
        topology_sha256=topology.digest,
        architecture_id=topology.architecture_id,
        layers=topology.layers,
        query_heads=topology.query_heads,
        kv_heads=topology.kv_heads,
        model_dimension=topology.width,
        feed_forward_dimension=topology.ffn_dimension,
        context_length=topology.context,
        compatibility_ref=None,
    )


def _lineage(generation: AuthenticatedGeneration) -> FactoryRunLineage:
    run = run_ref(generation)
    return FactoryRunLineage(
        run_id=run.run_id,
        checkpoint_lineage_id=f"accepted-generation:{generation.manifest_sha256}",
        generation=run.generation,
        generation_manifest_sha256=generation.manifest_sha256,
        checkpoint_sha256=None,
        checkpoint_receipt_sha256=None,
        topology=_topology(generation),
    )


def _adoption_evidence(generation: AuthenticatedGeneration, release_sha256: str):
    event = next((item for item in generation.outbox
                  if item.get("event") == _ADOPTION_EVENT
                  and item.get("factory_release_sha256") == release_sha256), None)
    if event is None:
        return (), None
    refs = {
        generation.acceptance_sha256,
        *(value for key, value in event.items()
          if key.endswith("_sha256") and isinstance(value, str)),
    }
    return tuple(sorted(refs)), generation.acceptance_sha256


def accepted_factory_records(
        history: tuple[AuthenticatedGeneration, ...],
) -> tuple[FactoryCockpitSnapshot, ...]:
    """Expose only Factory facts already proven by accepted portable custody.

    Accepted BAMF history proves admitted release identity and exact run topology,
    but not the complete pre-admission candidate ledger or release manifest. Those
    absent facts remain visibly partial instead of being reconstructed by guesswork.
    """
    if not history:
        return ()
    by_release = defaultdict(list)
    semantic_by_release = {}
    for generation in history:
        run = run_ref(generation)
        by_release[run.factory_release_sha256].append(generation)
        prior = semantic_by_release.setdefault(
            run.factory_release_sha256, run.semantic_release_sha256)
        if prior != run.semantic_release_sha256:
            invalid("CONTROL_PLANE_FACTORY_SEMANTIC_RELEASE_DRIFT")

    current_release = run_ref(history[-1]).factory_release_sha256
    records = []
    for release_sha256, generations in sorted(by_release.items()):
        receipt_refs = set()
        admission_receipt = None
        source_refs = []
        for generation in generations:
            source_refs.append(f"bamf-manifest:{generation.manifest_sha256}")
            receipt_refs.add(generation.acceptance_sha256)
            adoption_refs, adoption_receipt = _adoption_evidence(generation, release_sha256)
            receipt_refs.update(adoption_refs)
            admission_receipt = admission_receipt or adoption_receipt
        meta = RecordMeta(
            record_id=f"factory-release:{release_sha256}",
            run=None,
            materialized_at=0,
            observed_at=None,
            as_of=None,
            coverage=CoverageState.PARTIAL,
            authority=AuthorityClass.DERIVED,
            source_refs=tuple(source_refs),
            evidence_refs=(),
            receipt_refs=tuple(sorted(receipt_refs)),
        )
        records.append(FactoryCockpitSnapshot(
            meta=meta,
            subject_kind=FactorySubjectKind.FACTORY_RELEASE,
            subject_sha256=release_sha256,
            factory_release_sha256=release_sha256,
            candidate_sha256=None,
            semantic_release_sha256=semantic_by_release[release_sha256],
            lifecycle_state=FactoryLifecycleStatus.ADMITTED,
            delivery_status=FactoryDeliveryStatus.NOT_EVIDENCED,
            currency_state=(FactoryCurrencyState.CURRENT
                            if release_sha256 == current_release
                            else FactoryCurrencyState.STALE),
            admission_authority=FactoryAdmissionAuthority.HUMAN_ONLY,
            grade_frontier=(),
            capability_ids=(),
            dependency_edges=(),
            blockers=(),
            promoted_capability_ids=(),
            debt_capability_ids=(),
            receipt_refs=tuple(sorted(receipt_refs)),
            qualification_receipt_sha256=None,
            admission_receipt_sha256=admission_receipt,
            lineage=tuple(_lineage(item) for item in generations),
        ))
    return tuple(records)


__all__ = ("accepted_factory_records",)
