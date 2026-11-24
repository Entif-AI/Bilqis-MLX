"""Read-only School projection of the exact admitted executable Factory release."""
from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import json

from bilqis_mlx.mission_control.contracts.model import CoverageState
from bilqis_mlx.mission_control.contracts.envelopes import UnavailableEnvelope, UnavailableReason
from bilqis_mlx.mission_control.contracts.snapshots import (
    CapabilitySnapshot, CurriculumFrontier, SchoolSnapshot,
)

from ..native_contracts import data_value, missing_value, record_meta, run_ref


def read_admitted_release(run_dir, generation):
    """Decode the accepted release, never the latest unadmitted Factory artifact.

    Historical/portable custody can omit the release artifact. In that case
    the catalogue has no School inventory evidence. A present invalid artifact
    is not an alternative source of truth.
    """
    from bilqis_mlx.runtime.admission import _read_executable_factory_release_artifact

    digest = run_ref(generation).factory_release_sha256
    try:
        return _read_executable_factory_release_artifact(
            Path(run_dir), {
                "factory_release_sha256": digest,
                "factory_release_file": f"factory-releases/{digest}.json",
            })
    except (OSError, TypeError, ValueError, AttributeError):
        return None


def _bounded_names(names, *, budget=12_000):
    """Keep the wire summary small; the paginated capability roster is separate."""
    result = []
    size = 2
    for name in names:
        size += len(json.dumps(name, ensure_ascii=True).encode()) + 1
        if size > budget:
            break
        result.append(name)
    return tuple(result)


def admitted_school_records(generation, release, existing):
    """Admission is not mastery, readiness, or evidence of a teaching visit."""
    run = run_ref(generation)
    if release is None:
        return (UnavailableEnvelope(
            record_meta(f"school-unavailable:{run.run_id}:{run.generation}",
                        run, generation, coverage=CoverageState.UNKNOWN),
            f"school:{run.run_id}", UnavailableReason.UNAVAILABLE,
            f"factory-release:{run.factory_release_sha256}"),)
    ref = f"factory-release:{release.release_sha256}"

    def meta(name):
        return record_meta(
            f"{name}:{run.run_id}:{run.generation}", run, generation,
            evidence_refs=(ref,), coverage=CoverageState.PARTIAL)

    plan = release.execution_plan
    ids = tuple(item.capability_id for item in plan.capabilities)
    known = {}
    for item in existing:
        if (type(item) is CapabilitySnapshot
                and item.meta.run.factory_release_sha256 == release.release_sha256):
            prior = known.get(item.capability_id)
            if prior is None or item.meta.run.generation > prior.meta.run.generation:
                known[item.capability_id] = item
    records = [
        SchoolSnapshot(
            meta("school"), "ADMITTED", None,
            _bounded_names(item.grade_id for item in plan.grades),
            data_value(len(ids)), missing_value()),
        CurriculumFrontier(
            meta("curriculum-admission"), ref, (), (), _bounded_names(ids)),
    ]
    # Keep existing exact accepted visit scores. Unvisited admitted capabilities
    # get a roster row with missing scores, never a synthetic zero or mastery.
    for item in plan.capabilities:
        prior = known.get(item.capability_id)
        if prior is not None and prior.meta.run.generation == run.generation:
            continue
        if prior is not None:
            # An as-of tip roster may carry a prior measurement, but not relabel
            # that measurement as a newly completed examination.
            records.append(replace(
                prior, status="LAST_MEASURED",
                meta=replace(
                    prior.meta, run=run, coverage=CoverageState.PARTIAL,
                    record_id=f"school-last-measured:{run.run_id}:{run.generation}:{item.capability_id}",
                    evidence_refs=tuple(dict.fromkeys(
                        (*prior.meta.evidence_refs, prior.meta.record_id, ref))))))
        else:
            records.append(CapabilitySnapshot(
                record_meta(
                    f"admitted:{run.run_id}:{run.generation}:{item.capability_id}",
                    run, generation, evidence_refs=(ref,),
                    coverage=CoverageState.PARTIAL),
                item.capability_id, item.grade_id, "ADMITTED",
                missing_value(), missing_value(), missing_value()))
    return tuple(records)
