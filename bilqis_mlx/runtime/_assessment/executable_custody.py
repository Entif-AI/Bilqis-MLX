"""Executable-v2 assessment draw and durable cohort custody."""
from __future__ import annotations

import json

from ...factory.assessment import AssessmentScopeContract, assessment_scope_contract
from ...factory.executable_release import ExecutableFactoryRelease
from ...factory.generation import draw_executable_release_rows
from ...factory.adapters import SourceAdapterRegistry
from ...generated_assessment import EXECUTABLE_COHORT_SCHEMA, make_cohort, verify_stored_cohort
from ..state import _durable_json

def _draw_executable_scope_cohort(
        source_root, graph, release: ExecutableFactoryRelease,
        registry: SourceAdapterRegistry, *, capabilities, seed: int):
    """Draw one exact v2 assessment scope without deriving grade identity."""
    if type(seed) is not int:
        raise TypeError("FACTORY_EXECUTABLE_COHORT_SEED_REQUIRED")
    contract = assessment_scope_contract(release, capabilities)
    rows = []
    for capability in contract.capabilities:
        rows.extend(draw_executable_release_rows(
            source_root, graph, release, registry,
            seed=seed, capability=capability))
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
    try:
        cohort = verify_stored_cohort(
            stored, sha, expected_rubric_sha256=contract.rubric_sha256,
            expected_factory_release_sha256=release.release_sha256)
    except ValueError as exc:
        raise ValueError("FACTORY_EXECUTABLE_COHORT_CONTENT_DRIFT") from exc
    return cohort
