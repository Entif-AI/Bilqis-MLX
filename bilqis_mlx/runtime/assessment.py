"""Source cohort persistence and routine, promotion and generalization lifetimes."""
from __future__ import annotations

import json
from collections import Counter

from ..factory.assessment import (
    AssessmentScopeContract,
    assessment_scope_contract,
)
from ..factory.executable_release import ExecutableFactoryRelease
from ..factory.generation import draw_executable_release_rows
from ..factory.adapters import SourceAdapterRegistry
from ..generated_assessment import (
    GENERALIZATION_LIFECYCLE, PROMOTION_ATTEMPT_LIFECYCLE,
    ROUTINE_EVAL_LIFECYCLE, make_cohort,
)
from ..live_curriculum import cohort_contract as _cohort_contract, draw_course_rows, lesson_contract
from bilqis_mlx.curriculum.scheduler import assessment_capabilities
from bilqis_mlx.learning.stagnation_control import quarantined_capabilities
from .state import _durable_json, _seed, _state_from_json

EXECUTABLE_COHORT_SCHEMA = "bilqis.mlx.generated-cohort/v2"


def _draw_executable_scope_cohort(
        source_root, graph, release: ExecutableFactoryRelease,
        registry: SourceAdapterRegistry, *, capabilities, seed: int,
        legacy_course=None):
    """Draw one exact v2 assessment scope without deriving grade identity."""
    if type(seed) is not int:
        raise TypeError("FACTORY_EXECUTABLE_COHORT_SEED_REQUIRED")
    contract = assessment_scope_contract(release, capabilities)
    rows = []
    for capability in contract.capabilities:
        rows.extend(draw_executable_release_rows(
            source_root, graph, release, registry,
            seed=seed, legacy_course=legacy_course,
            capability=capability))
    cohort = make_cohort(
        rows,
        generator_version=contract.generator_version,
        seed=seed,
        rubric_version=contract.rubric_sha256,
    )
    return cohort, contract


def _persist_executable_cohort(
        run_dir, manifest, contract: AssessmentScopeContract, cohort):
    """Persist exact v2 cohort custody with source/rubric/release identities split."""
    if not isinstance(contract, AssessmentScopeContract):
        raise TypeError("FACTORY_EXECUTABLE_COHORT_CONTRACT_REQUIRED")
    if (cohort.generator_version != contract.generator_version or
            cohort.rubric_version != contract.rubric_sha256):
        raise ValueError("FACTORY_EXECUTABLE_COHORT_CONTRACT_DRIFT")
    source_manifest_sha256 = manifest.get("manifest_sha256")
    if not isinstance(source_manifest_sha256, str):
        raise ValueError("FACTORY_EXECUTABLE_COHORT_SOURCE_MANIFEST_REQUIRED")
    directory = run_dir / "cohorts"
    path = directory / (cohort.digest + ".json")
    if directory.is_symlink():
        raise ValueError("FACTORY_EXECUTABLE_COHORT_UNSAFE_DIRECTORY")
    payload = {
        "schema": EXECUTABLE_COHORT_SCHEMA,
        "factory_release_sha256": contract.factory_release_sha256,
        "semantic_catalog_sha256": contract.semantic_catalog_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "capabilities": list(contract.capabilities),
        "rubric_sha256": contract.rubric_sha256,
        "source_sha256": contract.source_sha256,
        "generator_version": contract.generator_version,
        "seed": cohort.seed,
        "cohort_sha256": cohort.digest,
        "rows": list(cohort.rows),
    }
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text()) != payload:
            raise ValueError("FACTORY_EXECUTABLE_COHORT_CUSTODY_DRIFT")
    else:
        _durable_json(path, payload)
    if json.loads(path.read_text()) != payload:
        raise ValueError("FACTORY_EXECUTABLE_COHORT_WRITEBACK_DRIFT")
    return {
        "schema": EXECUTABLE_COHORT_SCHEMA,
        "factory_release_sha256": contract.factory_release_sha256,
        "capabilities": list(contract.capabilities),
        "rubric_sha256": contract.rubric_sha256,
        "source_sha256": contract.source_sha256,
        "cohort_sha256": cohort.digest,
        "cohort_file": str(path.relative_to(run_dir)),
        "cohort_seed": cohort.seed,
    }


def _load_executable_cohort(
        run_dir, manifest, release: ExecutableFactoryRelease,
        capabilities, pointer):
    """Cold-read one current v2 cohort against its exact active scope."""
    if not isinstance(pointer, dict):
        raise ValueError("FACTORY_EXECUTABLE_COHORT_POINTER_INVALID")
    contract = assessment_scope_contract(release, capabilities)
    if pointer.get("factory_release_sha256") != release.release_sha256:
        raise ValueError("FACTORY_EXECUTABLE_COHORT_RELEASE_DRIFT")
    if (tuple(pointer.get("capabilities", ())) != contract.capabilities or
            pointer.get("rubric_sha256") != contract.rubric_sha256 or
            pointer.get("source_sha256") != contract.source_sha256):
        raise ValueError("FACTORY_EXECUTABLE_COHORT_SCOPE_DRIFT")
    sha = pointer.get("cohort_sha256")
    path_ref = pointer.get("cohort_file")
    if (not isinstance(sha, str) or len(sha) != 64 or
            path_ref != "cohorts/" + sha + ".json"):
        raise ValueError("FACTORY_EXECUTABLE_COHORT_POINTER_DRIFT")
    path = run_dir / path_ref
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("FACTORY_EXECUTABLE_COHORT_MISSING")
    stored = json.loads(path.read_text())
    if (stored.get("schema") != EXECUTABLE_COHORT_SCHEMA or
            stored.get("factory_release_sha256") != release.release_sha256 or
            stored.get("semantic_catalog_sha256") !=
            release.semantic_catalog_sha256 or
            stored.get("source_manifest_sha256") !=
            manifest.get("manifest_sha256") or
            tuple(stored.get("capabilities", ())) != contract.capabilities or
            stored.get("rubric_sha256") != contract.rubric_sha256 or
            stored.get("source_sha256") != contract.source_sha256 or
            stored.get("generator_version") != contract.generator_version or
            stored.get("cohort_sha256") != sha or
            stored.get("seed") != pointer.get("cohort_seed")):
        raise ValueError("FACTORY_EXECUTABLE_COHORT_METADATA_DRIFT")
    cohort = make_cohort(
        stored["rows"],
        generator_version=contract.generator_version,
        seed=stored["seed"],
        rubric_version=contract.rubric_sha256,
    )
    if cohort.digest != sha:
        raise ValueError("FACTORY_EXECUTABLE_COHORT_CONTENT_DRIFT")
    return cohort


def _routine_executable_cohort(
        run_dir, receipt, manifest, release, registry, source_root, graph, *,
        capabilities, assessment_epoch: int, legacy_course=None):
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
        capabilities=contract.capabilities, seed=seed,
        legacy_course=legacy_course)
    pointer = _persist_executable_cohort(
        run_dir, manifest, actual, cohort)
    return cohort, {
        **pointer,
        "policy": ROUTINE_EVAL_LIFECYCLE,
        "assessment_epoch": assessment_epoch,
    }


def _promotion_executable_cohort(
        run_dir, receipt, manifest, release, registry, source_root, graph, *,
        capabilities, assessment_epoch: int, legacy_course=None):
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
        capabilities=contract.capabilities, seed=seed,
        legacy_course=legacy_course)
    pointer = _persist_executable_cohort(
        run_dir, manifest, actual, cohort)
    return cohort, {
        **pointer,
        "policy": PROMOTION_ATTEMPT_LIFECYCLE,
        "assessment_epoch": assessment_epoch,
    }


def _generalization_executable_cohort(
        run_dir, receipt, manifest, release, registry, source_root, graph, *,
        capabilities, assessment_epoch: int, promotion_pointer,
        exposed_specimen_ids=(), legacy_course=None):
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
    burned_digests = set()
    burned_specimen_sets = set()
    for pointer in burned:
        previous = _load_executable_cohort(
            run_dir, manifest, release, contract.capabilities, pointer)
        burned_digests.add(previous.digest)
        burned_specimen_sets.add(
            frozenset(row["id"] for row in previous.rows))

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
            capabilities=contract.capabilities, seed=seed,
            legacy_course=legacy_course)
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
        capabilities, legacy_course=None):
    """Fresh exact-scope checkpoint-candidate screen under the admitted v2 release."""
    contract = assessment_scope_contract(release, capabilities)
    seed = _seed(
        receipt,
        capability="CANDIDATE_SCOPE:" + contract.rubric_sha256,
    )
    cohort, actual = _draw_executable_scope_cohort(
        source_root, graph, release, registry,
        capabilities=contract.capabilities, seed=seed,
        legacy_course=legacy_course)
    pointer = _persist_executable_cohort(
        run_dir, manifest, actual, cohort)
    return cohort, pointer


def _draw_live_rows(source_root, graph, *, seed, capability=None, each=None, course=None):
    """Draw only through the verified course/factory source boundary."""
    if course is None:
        raise ValueError("FACTORY_RELEASE_REQUIRED_FOR_SOURCE_GENERATION")
    return draw_course_rows(source_root, graph, course, seed=seed,
                            capability=capability, each=each)


def _persist_live_cohort(run_dir, manifest, course, cohort):
    """Make generation retry safe if a crash follows cohort publication."""
    rubric, release, generator, code_sha = _cohort_contract(course)
    if cohort.generator_version != generator or cohort.rubric_version != release:
        raise ValueError("HUMAN_TRAINER_COHORT_VERSION_MISMATCH")
    path = run_dir / "cohorts" / (cohort.digest + ".json")
    payload = {"schema": release,
               "source_manifest_sha256": manifest["manifest_sha256"],
               "rubric_sha256": rubric,
               "generator_version": generator,
               "generator_code_sha256": code_sha,
               "seed": cohort.seed,
               "cohort_sha256": cohort.digest, "rows": list(cohort.rows)}
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text()) != payload:
            raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_CUSTODY_DRIFT")
    else:
        _durable_json(path, payload)
    if json.loads(path.read_text()) != payload:
        raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_WRITEBACK_DRIFT")
    return str(path.relative_to(run_dir))


def _load_current_cohort(run_dir, manifest, course, pointer):
    """Read back one current-release cohort without changing its qualification state."""
    if not isinstance(pointer, dict):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_INVALID")
    sha = pointer.get("cohort_sha256")
    path_ref = pointer.get("cohort_file")
    if (not isinstance(sha, str) or len(sha) != 64 or
            path_ref != "cohorts/" + sha + ".json"):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_DRIFT")
    path = run_dir / path_ref
    if path.is_symlink() or not path.is_file():
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_MISSING")
    stored = json.loads(path.read_text())
    rubric, release, generator, code_sha = _cohort_contract(course)
    if (stored.get("schema") != release or
            stored.get("source_manifest_sha256") != manifest["manifest_sha256"] or
            stored.get("rubric_sha256") != rubric or
            stored.get("generator_version") != generator or
            stored.get("generator_code_sha256") != code_sha or
            stored.get("cohort_sha256") != sha or
            stored.get("seed") != pointer.get("cohort_seed")):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_METADATA_DRIFT")
    cohort = make_cohort(stored["rows"], generator_version=generator,
                         seed=stored["seed"], rubric_version=release)
    if cohort.digest != sha:
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_CONTENT_DRIFT")
    return cohort


def load_championship_cohort(run_dir, witness):
    """Verify an immutable earning cohort against its own admitted source identity."""
    sha = witness.get("cohort_sha256")
    if (not isinstance(sha, str) or len(sha) != 64 or
            any(char not in "0123456789abcdef" for char in sha)):
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_IDENTITY_REQUIRED")
    path = run_dir / "cohorts" / (sha + ".json")
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_MISSING")
    stored = json.loads(path.read_text())
    source_rubric = witness.get(
        "cohort_rubric_sha256", witness["rubric_sha256"])
    if (stored.get("cohort_sha256") != sha or
            stored.get("rubric_sha256") != source_rubric or
            stored.get("source_manifest_sha256") != witness["source_oracle_sha256"]):
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_SOURCE_DRIFT")
    rubric_version = (
        stored["rubric_sha256"]
        if stored.get("schema") == EXECUTABLE_COHORT_SCHEMA
        else stored["schema"])
    cohort = make_cohort(
        stored["rows"], generator_version=stored["generator_version"],
        seed=stored["seed"], rubric_version=rubric_version)
    if cohort.digest != sha:
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_CONTENT_DRIFT")
    return cohort


def _verify_saved_cohort(run_dir, receipt, course, *, sealed_v1_release=None):
    exam = receipt.get("last_exam") or {}
    if exam.get("cohort_sha256") is None:
        return None
    if (receipt.get("factory_admission_v2") is not None and
            exam.get("factory_release_sha256") is not None):
        from .admission import _read_executable_factory_release_artifact
        release = _read_executable_factory_release_artifact(run_dir, receipt)
        capabilities = tuple(exam.get("capabilities", ()))
        if not capabilities:
            raise ValueError("FACTORY_EXECUTABLE_SAVED_COHORT_SCOPE_REQUIRED")
        pointer = {
            key: exam[key] for key in (
                "factory_release_sha256", "capabilities", "rubric_sha256",
                "source_sha256", "cohort_sha256", "cohort_file",
                "cohort_seed")
            if key in exam
        }
        return _load_executable_cohort(
            run_dir,
            {"manifest_sha256": receipt["source_manifest_sha256"]},
            release, capabilities, pointer)
    from ..compatibility.assessment import verify_legacy_saved_cohort
    return verify_legacy_saved_cohort(
        run_dir, receipt, course, sealed_v1_release=sealed_v1_release)


def _grade_test_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Draw a fresh routine school-evaluation cohort at every exam boundary.

    Routine MAIN/RECOVERY evaluation is deliberately distinct from any
    promotion/graduation qualification attempt. Persisting a prior
    qualification_cohort must never freeze ordinary school evaluation.
    """
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(
        receipt,
        capability=f"ROUTINE_GRADE_EVAL:{school.grade}:{school.grade_exam_epoch}",
    )
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed, rubric_version=release)
    cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort, {"policy": ROUTINE_EVAL_LIFECYCLE,
                    "assessment_grade": school.grade,
                    "grade_exam_epoch": school.grade_exam_epoch,
                    "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                    "cohort_seed": cohort.seed}


def _promotion_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Materialize one distinct promotion-attempt cohort.

    The attempt is deterministic and crash-retry safe within the same durable
    generation, but a later promotion attempt receives a new seed and cohort.
    """
    school = _state_from_json(receipt["school"], course)
    existing = receipt.get("qualification_cohort")
    if (isinstance(existing, dict) and
            existing.get("policy") == PROMOTION_ATTEMPT_LIFECYCLE and
            existing.get("assessment_grade") == school.grade and
            existing.get("grade_exam_epoch") == school.grade_exam_epoch):
        return _load_current_cohort(run_dir, manifest, course, existing), dict(existing)
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(
        receipt,
        capability=f"PROMOTION_ATTEMPT:{school.grade}:{school.grade_exam_epoch}",
    )
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed, rubric_version=release)
    cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort, {"policy": PROMOTION_ATTEMPT_LIFECYCLE,
                    "assessment_grade": school.grade,
                    "grade_exam_epoch": school.grade_exam_epoch,
                    "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                    "cohort_seed": cohort.seed}


def _generalization_cohort(run_dir, receipt, manifest, course, source_root, graph,
                           *, promotion_sha256: str, exposed_specimen_ids=()):
    """Draw a never-reused fresh qualification cohort after promotion passes."""
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    burned = receipt.get("burned_generalization_cohorts", ())
    if (not isinstance(burned, (tuple, list)) or
            any(not isinstance(item, str) or len(item) != 64 or
                any(char not in "0123456789abcdef" for char in item) for item in burned)):
        raise ValueError("HUMAN_TRAINER_GENERALIZATION_BURN_LEDGER_INVALID")
    excluded = set(exposed_specimen_ids)
    # A burn invalidates the prior *measurement instrument*, not every
    # correctly answered specimen forever. Training-exposed misses remain
    # excluded below, while an exact prior specimen set may never recur.
    burned_specimen_sets = set()
    for digest in (promotion_sha256, *burned):
        path = run_dir / "cohorts" / (digest + ".json")
        if path.is_symlink() or not path.is_file():
            raise ValueError("HUMAN_TRAINER_GENERALIZATION_EXPOSURE_EVIDENCE_MISSING")
        payload = json.loads(path.read_text())
        previous = make_cohort(payload["rows"], seed=payload["seed"],
                               generator_version=payload["generator_version"],
                               rubric_version=payload["schema"])
        if previous.digest != digest or payload.get("cohort_sha256") != digest:
            raise ValueError("HUMAN_TRAINER_GENERALIZATION_EXPOSURE_CONTENT_DRIFT")
        specimen_ids = frozenset(row["id"] for row in previous.rows)
        if digest == promotion_sha256:
            excluded.update(specimen_ids)
        else:
            burned_specimen_sets.add(specimen_ids)
    excluded.update(row["id"] for row in receipt.get("teacher_misses", ()))
    required = None
    selected = {}
    for attempt in range(128):
        seed = _seed(
            receipt,
            capability=f"GENERALIZATION:{school.grade}:{school.grade_exam_epoch}:{len(burned)}",
            step=attempt,
        )
        rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
        if required is None:
            required = Counter(_generalization_stratum(row) for row in rows)
        for row in rows:
            key = _generalization_stratum(row)
            if row["id"] not in excluded and len(selected.get(key, ())) < required[key]:
                selected.setdefault(key, []).append(row)
                excluded.add(row["id"])
        if any(len(selected.get(key, ())) != count for key, count in required.items()):
            continue
        cohort = make_cohort(
            [row for key in required for row in selected[key]],
            generator_version=generator, seed=seed, rubric_version=release)
        if (cohort.digest == promotion_sha256 or cohort.digest in burned or
                frozenset(row["id"] for row in cohort.rows) in burned_specimen_sets):
            continue
        cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
        return cohort, {"policy": GENERALIZATION_LIFECYCLE,
                        "assessment_grade": school.grade,
                        "grade_exam_epoch": school.grade_exam_epoch,
                        "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                        "cohort_seed": cohort.seed}
    raise ValueError("HUMAN_TRAINER_FRESH_GENERALIZATION_COHORT_EXHAUSTED")


def _generalization_stratum(row):
    """Keep the source draw's answer, operand-pattern and world-shape coverage."""
    return (row["capability"], row.get("answer_kind", "binary"), row["gold"],
            tuple(row.get("operand_truths", ())), row.get("universe_size"))


def _candidate_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Fresh randomized qualification for checkpoint candidates, not graduation."""
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(receipt, capability="CANDIDATE_CHECKPOINT")
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(rows, generator_version=generator, seed=seed,
                         rubric_version=release)
    _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort


def _introduced_cohort(run_dir, manifest, course, school, cohort):
    """Activate only already introduced concepts from this generated cohort."""
    eligible = set(assessment_capabilities(course, school))
    rows = tuple(row for row in cohort.rows if row["capability"] in eligible)
    selected = cohort if rows == cohort.rows else make_cohort(rows,
        generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    return selected, _persist_live_cohort(run_dir, manifest, course, selected)


def _without_stagnant_capabilities(run_dir, manifest, course, cohort,
                                   control):
    """Remove current-session containment debt from ordinary evaluation only."""
    blocked = set(quarantined_capabilities(control))
    if not blocked:
        return cohort, _persist_live_cohort(run_dir, manifest, course, cohort)
    rows = tuple(row for row in cohort.rows if row["capability"] not in blocked)
    _require_active_stagnation_scope(rows)
    selected = make_cohort(
        rows, generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    return selected, _persist_live_cohort(run_dir, manifest, course, selected)


def _require_active_stagnation_scope(scope) -> None:
    if not scope:
        raise ValueError("STAGNATION_ROUTINE_EVALUATION_HAS_NO_ACTIVE_CAPABILITIES")
