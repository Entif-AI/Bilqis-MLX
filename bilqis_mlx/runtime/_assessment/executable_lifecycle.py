"""Executable-v2 routine, promotion, generalization and candidate cohorts."""
from __future__ import annotations

from collections import Counter

from ...factory.assessment import assessment_scope_contract
from ...generated_assessment import (GENERALIZATION_LIFECYCLE,
    PROMOTION_ATTEMPT_LIFECYCLE, ROUTINE_EVAL_LIFECYCLE, make_cohort)
from ..state import _seed
from .common import _generalization_stratum
from .executable_custody import (_draw_executable_scope_cohort,
    _load_executable_cohort, _persist_executable_cohort)

def _routine_executable_cohort(
        run_dir, receipt, manifest, release, registry, source_root, graph, *,
        capabilities, assessment_epoch: int):
    """Draw a fresh exact-scope routine cohort at every assessment boundary."""
    contract = assessment_scope_contract(release, capabilities)
    seed = _seed(
        receipt,
        capability=(
            "ROUTINE_SCOPE:"
            + contract.rubric_sha256 + ":" + str(assessment_epoch)),
    )
    cohort, actual = _draw_executable_scope_cohort(
        source_root, graph, release, registry,
        capabilities=contract.capabilities, seed=seed)
    pointer = _persist_executable_cohort(
        run_dir, manifest, actual, cohort)
    return cohort, {
        **pointer,
        "policy": ROUTINE_EVAL_LIFECYCLE,
        "assessment_epoch": assessment_epoch,
    }


def _promotion_executable_cohort(
        run_dir, receipt, manifest, release, registry, source_root, graph, *,
        capabilities, assessment_epoch: int):
    """Keep one exact-scope promotion instrument fixed only within its attempt."""
    contract = assessment_scope_contract(release, capabilities)
    existing = receipt.get("qualification_cohort_v2")
    if (isinstance(existing, dict) and
            existing.get("policy") == PROMOTION_ATTEMPT_LIFECYCLE and
            existing.get("assessment_epoch") == assessment_epoch and
            tuple(existing.get("capabilities", ())) == contract.capabilities):
        return (
            _load_executable_cohort(
                run_dir, manifest, release, contract.capabilities, existing),
            dict(existing),
        )
    seed = _seed(
        receipt,
        capability=(
            "PROMOTION_SCOPE:"
            + contract.rubric_sha256 + ":" + str(assessment_epoch)),
    )
    cohort, actual = _draw_executable_scope_cohort(
        source_root, graph, release, registry,
        capabilities=contract.capabilities, seed=seed)
    pointer = _persist_executable_cohort(
        run_dir, manifest, actual, cohort)
    return cohort, {
        **pointer,
        "policy": PROMOTION_ATTEMPT_LIFECYCLE,
        "assessment_epoch": assessment_epoch,
    }


def _burned_generalization_evidence(
        run_dir, manifest, current_release, burned):
    """Verify permanent burned cohorts under each pointer's own v2 release."""
    digests = set()
    specimen_sets = set()
    for pointer in burned:
        pointer_release_sha = pointer.get("factory_release_sha256")
        if pointer_release_sha == current_release.release_sha256:
            pointer_release = current_release
        else:
            from ..admission import _read_executable_factory_release_artifact
            pointer_release = _read_executable_factory_release_artifact(
                run_dir, {
                    "factory_release_sha256": pointer_release_sha,
                    "factory_release_file": (
                        "factory-releases/" + str(pointer_release_sha) + ".json"),
                })
        previous = _load_executable_cohort(
            run_dir, manifest, pointer_release,
            tuple(pointer.get("capabilities", ())), pointer)
        digests.add(previous.digest)
        specimen_sets.add(frozenset(row["id"] for row in previous.rows))
    return digests, specimen_sets


def _generalization_executable_cohort(
        run_dir, receipt, manifest, release, registry, source_root, graph, *,
        capabilities, assessment_epoch: int, promotion_pointer,
        exposed_specimen_ids=()):
    """Draw a fresh exact-scope generalization instrument after promotion."""
    contract = assessment_scope_contract(release, capabilities)
    promotion = _load_executable_cohort(
        run_dir, manifest, release, contract.capabilities, promotion_pointer)
    burned = receipt.get("burned_generalization_cohorts_v2", ())
    if not isinstance(burned, (tuple, list)):
        raise ValueError(
            "FACTORY_EXECUTABLE_GENERALIZATION_BURN_LEDGER_INVALID")

    excluded = set(exposed_specimen_ids)
    excluded.update(row["id"] for row in promotion.rows)
    excluded.update(row["id"] for row in receipt.get("teacher_misses", ()))
    base_excluded = set(excluded)
    # Permanent instrument history retains its original release authority; a
    # later profile may legitimately disable some capabilities from that scope.
    burned_digests, burned_specimen_sets = _burned_generalization_evidence(
        run_dir, manifest, release, burned)

    required = None
    selected = {}
    for attempt in range(128):
        seed = _seed(
            receipt,
            capability=(
                "GENERALIZATION_SCOPE:"
                + contract.rubric_sha256 + ":"
                + str(assessment_epoch) + ":" + str(len(burned))),
            step=attempt,
        )
        rows, actual = _draw_executable_scope_cohort(
            source_root, graph, release, registry,
            capabilities=contract.capabilities, seed=seed)
        if required is None:
            required = Counter(
                _generalization_stratum(row) for row in rows.rows)
        for row in rows.rows:
            key = _generalization_stratum(row)
            if (row["id"] not in excluded and
                    len(selected.get(key, ())) < required[key]):
                selected.setdefault(key, []).append(row)
                excluded.add(row["id"])
        if any(
                len(selected.get(key, ())) != count
                for key, count in required.items()):
            continue
        cohort = make_cohort(
            [row for key in required for row in selected[key]],
            generator_version=actual.generator_version,
            seed=seed,
            rubric_version=actual.rubric_sha256)
        specimen_set = frozenset(row["id"] for row in cohort.rows)
        if (cohort.digest == promotion.digest or
                cohort.digest in burned_digests or
                specimen_set in burned_specimen_sets):
            selected = {}
            # Burning an assessment instrument forbids repeating that cohort,
            # not reusing its still-unexposed source-valid specimens in a new
            # combination. Preserve only true contamination exclusions.
            excluded = set(base_excluded)
            continue
        pointer = _persist_executable_cohort(
            run_dir, manifest, actual, cohort)
        return cohort, {
            **pointer,
            "policy": GENERALIZATION_LIFECYCLE,
            "assessment_epoch": assessment_epoch,
        }
    raise ValueError("FACTORY_EXECUTABLE_FRESH_GENERALIZATION_COHORT_EXHAUSTED")


def _candidate_executable_cohort(
        run_dir, receipt, manifest, release, registry, source_root, graph, *,
        capabilities):
    """Fresh exact-scope checkpoint-candidate screen under the admitted v2 release."""
    contract = assessment_scope_contract(release, capabilities)
    seed = _seed(
        receipt,
        capability="CANDIDATE_SCOPE:" + contract.rubric_sha256,
    )
    cohort, actual = _draw_executable_scope_cohort(
        source_root, graph, release, registry,
        capabilities=contract.capabilities, seed=seed)
    pointer = _persist_executable_cohort(
        run_dir, manifest, actual, cohort)
    return cohort, pointer
