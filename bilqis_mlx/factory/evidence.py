"""Neural-inert execution of one autonomous learner-evidence obligation."""
from __future__ import annotations

import hashlib
import json

from ..generated_assessment import make_cohort, score
from .adapters import SourceAdapterRegistry
from .autonomy import EvidenceKind, EvidenceObligation, EvidenceReceipt
from .generation import draw_release_rows
from .model import FactoryRelease


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def draw_evidence_rows(source_root, graph, release: FactoryRelease,
                       registry: SourceAdapterRegistry,
                       obligation: EvidenceObligation, *, seed: int,
                       max_rounds: int = 8) -> tuple[dict, ...]:
    """Materialize fresh source-checked rows that actually witness obligation."""
    release.verify()
    if not isinstance(registry, SourceAdapterRegistry):
        raise TypeError("FACTORY_EVIDENCE_REGISTRY_REQUIRED")
    if not isinstance(obligation, EvidenceObligation):
        raise TypeError("FACTORY_EVIDENCE_OBLIGATION_REQUIRED")
    if obligation.capability_id not in release.course.capability_map:
        raise ValueError("FACTORY_EVIDENCE_UNKNOWN_CAPABILITY")
    if type(seed) is not int or type(max_rounds) is not int or max_rounds < 1:
        raise ValueError("FACTORY_EVIDENCE_DRAW_ARGUMENT_INVALID")

    target = obligation.minimum_specimens
    each = target if obligation.kind is EvidenceKind.DIRECT else max(8, target * 4)
    found: dict[str, dict] = {}
    for round_index in range(max_rounds):
        rows = draw_release_rows(
            source_root, graph, release, registry,
            seed=seed + round_index,
            capability=obligation.capability_id,
            each=each,
        )
        for row in rows:
            if registry.obligation_witness(
                    release.course, capability=obligation.capability_id,
                    row=row, obligation=obligation,
                    source_root=source_root, graph=graph):
                found[row["id"]] = row
                if len(found) >= target:
                    return tuple(found[key] for key in sorted(found)[:target])
    raise ValueError(
        "FACTORY_EVIDENCE_WITNESS_EXHAUSTED:" + obligation.obligation_id)


def measure_evidence(source_root, graph, release: FactoryRelease,
                     registry: SourceAdapterRegistry,
                     obligation: EvidenceObligation, *,
                     checkpoint: dict, seed: int, predictor) -> EvidenceReceipt:
    """Score one intact checkpoint on a fresh obligation-specific cohort."""
    if not callable(predictor):
        raise TypeError("FACTORY_EVIDENCE_PREDICTOR_REQUIRED")
    rows = draw_evidence_rows(
        source_root, graph, release, registry, obligation, seed=seed)
    cap = release.course.capability_map[obligation.capability_id]
    cohort = make_cohort(
        rows,
        generator_version=cap.lesson_generator,
        seed=seed,
        rubric_version=(
            release.release_sha256 + "/" + obligation.obligation_id),
    )
    predictions = predictor(tuple(rows))
    measured = score(cohort, predictions, checkpoint)
    evidence_id = _digest({
        "factory_release_sha256": release.release_sha256,
        "obligation_id": obligation.obligation_id,
        "cohort_sha256": cohort.digest,
        "checkpoint_sha256": checkpoint.get("sha256"),
        "optimizer_step": checkpoint.get("optimizer_step"),
        "predictions": sorted(predictions.items())
        if isinstance(predictions, dict) else None,
    })
    return EvidenceReceipt(
        obligation_id=obligation.obligation_id,
        evidence_id=evidence_id,
        checkpoint_sha256=checkpoint["sha256"],
        optimizer_step=checkpoint["optimizer_step"],
        cohort_sha256=cohort.digest,
        specimen_count=len(rows),
        passed=bool(measured["perfect_on_sample"]),
    )
