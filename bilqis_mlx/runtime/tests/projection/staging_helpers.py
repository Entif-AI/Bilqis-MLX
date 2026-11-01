"""Shared source-bound event fixtures for C10 projection proofs."""
from pathlib import Path
from bilqis_mlx.runtime.akasha_outbox import AkashaEvent, AkashaEventKind
from bilqis_mlx.runtime.bamf_projection import BamfProjectionEvent, ProjectionDomainContract


def _event(subject):
    return AkashaEvent.from_payload(
        kind=AkashaEventKind.REQUALIFICATION,
        subject_id=subject, source_receipt_sha256="9" * 64,
        payload={
            "capability_id": subject,
            "retained_generation_sha256": "a" * 64,
            "status": "REQUALIFICATION_REQUIRED",
        },
        source_time=570, effective_time=575,
        observed_at=580, recorded_at=585,
    )

def _contract(path):
    return ProjectionDomainContract(
        outbox_path=path,
        source_id="source:fixture",
        release_digest="1" * 64,
        model_digest="2" * 64,
        evaluator_digest="3" * 64,
        rights_digest="4" * 64,
        as_of=600,
    )

def _projected(event, contract):
    return BamfProjectionEvent(
        event=event,
        source_id=contract.source_id,
        release_digest=contract.release_digest,
        model_digest=contract.model_digest,
        evaluator_digest=contract.evaluator_digest,
        rights_digest=contract.rights_digest,
        as_of=contract.as_of,
    )
