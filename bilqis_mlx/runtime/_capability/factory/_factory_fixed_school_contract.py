"""C05 fixed-school receipt, scope, and cohort verification contracts."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.factory.assessment import assessment_scope_contract
from bilqis_mlx.generated_assessment import EXECUTABLE_COHORT_SCHEMA, verify_stored_cohort
from bilqis_mlx.runtime.bamf_bundle.codec import validate_bamf_bundle_custody
from bilqis_mlx.runtime.bamf_bundle.genesis.records import BamfRunIdentity
from bilqis_mlx.runtime.capability_evaluation import _invalid
from bilqis_mlx.semantics.domains import contract_digest

SCHEMA = "bilqis.mlx.c05-bamf-fixed-school/v1"
KEYS = {
    "schema", "run_id", "run_identity_sha256",
    "foundation_parent_manifest_sha256", "factory_release_sha256",
    "source_identity_sha256", "semantic_catalog_sha256", "capabilities",
    "rubric_sha256", "source_sha256", "generator_version", "seed",
    "cohort_sha256", "cohort_file", "cohort_seed",
}


def is_hex(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def expected_source_identity(release) -> str:
    value = (release.source_bindings.source_attestation_sha256
             or release.source_bindings.digest())
    if not is_hex(value):
        _invalid("BAMF_C05_FIXED_SCHOOL_SOURCE_IDENTITY_INVALID")
    return value


def scope(source_context, parent):
    release = source_context.release
    identity = parent.run_identity
    if identity is None:
        _invalid("BAMF_C05_BAMF_RUN_IDENTITY_REQUIRED")
    if identity.factory_release_sha256 != release.release_sha256:
        _invalid("BAMF_C05_FIXED_SCHOOL_FACTORY_RELEASE_DRIFT")
    capabilities = tuple(
        item.capability_id for item in release.execution_plan.capabilities)
    if not capabilities or any(not isinstance(item, str) or not item
                               for item in capabilities):
        _invalid("BAMF_C05_FIXED_SCHOOL_SCOPE_INVALID")
    contract = assessment_scope_contract(release, capabilities)
    source_identity = expected_source_identity(release)
    if identity.initial_source_identity != source_identity:
        _invalid("BAMF_C05_FIXED_SCHOOL_SOURCE_IDENTITY_DRIFT")
    return capabilities, contract, source_identity


def school_seed(identity, release, source_identity, capabilities, contract) -> int:
    digest = contract_digest({
        "schema": "bilqis.mlx.c05-bamf-fixed-school-seed/v1",
        "run_identity": identity.digest,
        "factory_release": release.release_sha256,
        "source_identity": source_identity,
        "semantic_catalog": release.semantic_catalog_sha256,
        "capabilities": capabilities,
        "rubric": contract.rubric_sha256,
        "source": contract.source_sha256,
    })
    return int(digest[:16], 16)


def pointer(receipt: dict) -> dict:
    return {
        "factory_release_sha256": receipt["factory_release_sha256"],
        "capabilities": list(receipt["capabilities"]),
        "rubric_sha256": receipt["rubric_sha256"],
        "source_sha256": receipt["source_sha256"],
        "cohort_sha256": receipt["cohort_sha256"],
        "cohort_file": receipt["cohort_file"],
        "cohort_seed": receipt["cohort_seed"],
    }


def load_trusted_complete_school(stored, source_manifest, release, capabilities, value):
    """Verify a trusted executable-cohort payload without reopening its projection."""
    contract = assessment_scope_contract(release, capabilities)
    if (not isinstance(stored, dict)
            or stored.get("schema") != EXECUTABLE_COHORT_SCHEMA
            or stored.get("factory_release_sha256") != release.release_sha256
            or stored.get("semantic_catalog_sha256") != release.semantic_catalog_sha256
            or stored.get("source_manifest_sha256") != source_manifest.get("manifest_sha256")
            or tuple(stored.get("capabilities", ())) != contract.capabilities
            or stored.get("rubric_sha256") != contract.rubric_sha256
            or stored.get("source_sha256") != contract.source_sha256
            or stored.get("generator_version") != contract.generator_version
            or stored.get("cohort_sha256") != value.get("cohort_sha256")
            or stored.get("seed") != value.get("cohort_seed")):
        _invalid("BAMF_C05_FIXED_SCHOOL_COHORT_DRIFT")
    try:
        return verify_stored_cohort(
            stored, value["cohort_sha256"],
            expected_rubric_sha256=contract.rubric_sha256,
            expected_factory_release_sha256=release.release_sha256,
            expected_capabilities=contract.capabilities)
    except ValueError:
        _invalid("BAMF_C05_FIXED_SCHOOL_COHORT_DRIFT")
        raise AssertionError


def _validate_foundation(source_context, parent, digest: str) -> None:
    foundation = Path(source_context.run_dir or "") / "bamf-bundles" / digest
    if (source_context.run_dir is None or foundation.is_symlink()
            or not foundation.is_dir()):
        _invalid("BAMF_C05_FIXED_SCHOOL_FOUNDATION_PARENT_INVALID")
    try:
        manifest = validate_bamf_bundle_custody(
            foundation, expected_manifest_sha256=digest)
        binding = manifest.get("sidecars", {}).get("run_identity")
        if not isinstance(binding, dict):
            raise ValueError
        record = json.loads((foundation / binding["filename"]).read_text())
        identity = BamfRunIdentity.from_record(record)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        _invalid("BAMF_C05_FIXED_SCHOOL_FOUNDATION_PARENT_INVALID")
        raise AssertionError
    if (manifest.get("run_id") != parent.run_id
            or identity.digest != parent.run_identity.digest):
        _invalid("BAMF_C05_FIXED_SCHOOL_FOUNDATION_PARENT_INVALID")


def require_receipt(
        receipt, *, source_context, parent, capabilities, contract,
        source_identity):
    if not isinstance(receipt, dict) or set(receipt) != KEYS:
        _invalid("BAMF_C05_FIXED_SCHOOL_RECEIPT_INVALID")
    identity = parent.run_identity
    digests = tuple(key for key in KEYS if key.endswith("_sha256"))
    expected_seed = school_seed(
        identity, source_context.release, source_identity, capabilities, contract)
    if (
        receipt["schema"] != SCHEMA
        or any(not isinstance(receipt[key], str) or not receipt[key]
               for key in ("run_id", "generator_version", "cohort_file"))
        or any(not is_hex(receipt[key]) for key in digests)
        or not isinstance(receipt["capabilities"], list)
        or any(not isinstance(value, str) or not value
               for value in receipt["capabilities"])
        or type(receipt["seed"]) is not int or receipt["seed"] < 0
        or type(receipt["cohort_seed"]) is not int or receipt["cohort_seed"] < 0
        or receipt["seed"] != receipt["cohort_seed"]
        or receipt["run_id"] != parent.run_id
        or receipt["run_identity_sha256"] != identity.digest
        or receipt["factory_release_sha256"] != source_context.release.release_sha256
        or receipt["source_identity_sha256"] != source_identity
        or receipt["semantic_catalog_sha256"] != source_context.release.semantic_catalog_sha256
        or tuple(receipt["capabilities"]) != capabilities
        or receipt["rubric_sha256"] != contract.rubric_sha256
        or receipt["source_sha256"] != contract.source_sha256
        or receipt["generator_version"] != contract.generator_version
        or receipt["seed"] != expected_seed
        or receipt["cohort_file"] != f"cohorts/{receipt['cohort_sha256']}.json"
    ):
        _invalid("BAMF_C05_FIXED_SCHOOL_RECEIPT_DRIFT")
    _validate_foundation(
        source_context, parent, receipt["foundation_parent_manifest_sha256"])
    return receipt
