"""Acceptance authentication and traversal for tensor-thin BAMF history."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
    ATLAS_ADMISSION_SCHEMA_V4,
    ATLAS_ADMISSION_SCHEMAS,
    AtlasAdmissionBinding,
    ParsedAtlasAdmissionBinding,
)
from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
    FACTORY_RELEASE_ADMISSION_SCHEMAS,
    FactoryReleaseAdmissionBinding,
    ParsedFactoryReleaseAdmissionBinding,
)
from bilqis_mlx.runtime.bamf_bundle.motif.transition import (
    is_motif_allocation_transition,
)
from bilqis_mlx.runtime.bamf_bundle.records import canonical, invalid, sha

from .historical_custody import (
    HistoricalBamfBundle,
    load_historical_bamf_bundle,
)
from .receipt import is_digest


def historical_accepted_binding_for_manifest(
        run_dir: Path,
        manifest_sha256: str,
        bundle: HistoricalBamfBundle,
        *,
        expected_acceptance_sha256: str,
        expected_candidate_identity_sha256: str | None,
):
    """Authenticate historical acceptance against immutable metadata and child linkage."""
    from bilqis_mlx.learning.atlas_acceptance import AcceptedCandidateBinding
    from bilqis_mlx.runtime.bamf_bundle.publication.storage import ACCEPTANCE_DIR

    path = Path(run_dir) / ACCEPTANCE_DIR / f"{manifest_sha256}.json"
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    try:
        record = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        invalid("BAMF_GENERATION_ACCEPTANCE_INVALID")

    if bundle.generation == 0:
        from bilqis_mlx.runtime.bamf_bundle.genesis import InitialGenerationBinding
        from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
            optimizer_hyperparameters_digest,
        )
        binding = InitialGenerationBinding.from_record(record)
        if (binding.digest != expected_acceptance_sha256
                or binding.run_id != bundle.run_id
                or binding.generation != bundle.generation
                or binding.feature_sha256 != bundle.extents.factor_map_digest
                or binding.optimizer_step != bundle.optimizer_step
                or bundle.run_identity is None
                or binding.run_identity_sha256 != bundle.run_identity.digest
                or binding.optimizer_hyperparameters_sha256
                   != optimizer_hyperparameters_digest(
                       bundle.optimizer_hyperparameters)):
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
        return binding

    schema = record.get("schema_version")
    if schema in FACTORY_RELEASE_ADMISSION_SCHEMAS:
        binding = FactoryReleaseAdmissionBinding.from_record(record)
    elif schema in ATLAS_ADMISSION_SCHEMAS:
        binding = AtlasAdmissionBinding.from_record(record)
    else:
        binding = AcceptedCandidateBinding.from_record(record)
    if (binding.digest != expected_acceptance_sha256
            or binding.run_id != bundle.run_id
            or binding.generation != bundle.generation
            or binding.feature_sha256 != bundle.extents.factor_map_digest
            or binding.optimizer_step != bundle.optimizer_step
            or (expected_candidate_identity_sha256 is not None
                and binding.candidate_identity_sha256
                    != expected_candidate_identity_sha256)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")

    if isinstance(binding, ParsedAtlasAdmissionBinding):
        if binding.schema_version == ATLAS_ADMISSION_SCHEMA_V4:
            state = bundle.championship_state
            if (state is None
                    or binding.championship_state_sha256
                       != sha(canonical(dict(state)))):
                invalid("BAMF_ATLAS_ADMISSION_BINDING_DRIFT")
    elif isinstance(binding, ParsedFactoryReleaseAdmissionBinding):
        transition_sha256 = sha(canonical(bundle.transition))
        if (binding.transition_sha256 != transition_sha256
                or not any(
                    isinstance(event, dict)
                    and event.get("transition_sha256") == transition_sha256
                    and event.get("generation") == bundle.generation
                    and event.get("optimizer_step") == bundle.optimizer_step
                    for event in bundle.outbox)):
            invalid("BAMF_FACTORY_RELEASE_ADMISSION_BINDING_DRIFT")
    else:
        _validate_generic_binding(record, binding, bundle)
    return binding


def _validate_generic_binding(record, binding, bundle) -> None:
    from bilqis_mlx.learning._retention._atlas_candidate.proofs import (
        CandidateStepProof,
    )
    proofs = record.get("step_proof_sha256")
    stored = bundle.records["step_proofs"].get("proofs", [])
    proof_digests = tuple(
        CandidateStepProof.from_record(item).digest for item in stored)
    if tuple(proofs or ()) != proof_digests:
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    if (getattr(binding, "source_authority_registry_sha256", None) is not None
            and binding.source_authority_registry_sha256
            != bundle.correction_frontier.get("source_authority_registry_sha256")):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    if (getattr(binding, "teacher_state_sha256", None) is not None
            and binding.teacher_state_sha256 != sha(canonical(bundle.teacher_state))):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    from bilqis_mlx.learning.atlas_acceptance import (
        EXACT_MOTIF_ACCEPTANCE_SCHEMA,
        EXACT_MOTIF_CLOSURE_ACCEPTANCE_SCHEMA,
        MOTIF_CLOSURE_ACCEPTANCE_SCHEMA,
    )
    if (binding.schema_version in {
            MOTIF_CLOSURE_ACCEPTANCE_SCHEMA,
            EXACT_MOTIF_ACCEPTANCE_SCHEMA,
            EXACT_MOTIF_CLOSURE_ACCEPTANCE_SCHEMA,
    } and not is_motif_allocation_transition(bundle.transition)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")


def load_historical_accepted_parent(
        run_dir: Path,
        child_manifest_sha256: str,
        child,
        child_binding,
):
    """Load one authenticated parent as metadata-only historical custody."""
    from .acceptance import parent_acceptance_anchor_from_manifest

    parent_manifest = child.parent_manifest_sha256
    if parent_manifest is None:
        return None, None
    parent_acceptance = parent_acceptance_anchor_from_manifest(
        Path(run_dir), child_manifest_sha256)
    expected_parent_identity = getattr(
        child_binding, "parent_candidate_identity_sha256", None)
    if parent_acceptance is None or not is_digest(expected_parent_identity):
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    parent = load_historical_bamf_bundle(
        Path(run_dir) / "bamf-bundles" / parent_manifest,
        expected_manifest_sha256=parent_manifest)
    binding = historical_accepted_binding_for_manifest(
        Path(run_dir), parent_manifest, parent,
        expected_acceptance_sha256=parent_acceptance,
        expected_candidate_identity_sha256=expected_parent_identity)
    if (parent.run_id != child.run_id
            or parent.generation + 1 != child.generation
            or parent.run_identity != child.run_identity):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    return parent, binding


def iter_accepted_bamf_history(
        run_dir: Path,
        *,
        current_manifest_sha256: str,
        current_acceptance_sha256: str,
        current,
):
    """Yield current executable custody, then authenticated tensor-thin ancestors."""
    from .acceptance import (
        accepted_binding_for_manifest,
        parent_acceptance_anchor_from_manifest,
    )

    root = Path(run_dir)
    manifest = current_manifest_sha256
    bundle = current
    acceptance = current_acceptance_sha256
    binding = accepted_binding_for_manifest(
        root, manifest, bundle, expected_acceptance_sha256=acceptance)
    while True:
        yield manifest, acceptance, bundle, binding
        if bundle.generation == 0:
            return
        parent_manifest = bundle.parent_manifest_sha256
        parent, parent_binding = load_historical_accepted_parent(
            root, manifest, bundle, binding)
        if parent is None or parent_binding is None or parent_manifest is None:
            return
        parent_acceptance = parent_acceptance_anchor_from_manifest(root, manifest)
        if parent_acceptance is None:
            return
        manifest, acceptance = parent_manifest, parent_acceptance
        bundle, binding = parent, parent_binding


def iter_historical_bamf_history(
        run_dir: Path,
        *,
        manifest_sha256: str,
        acceptance_sha256: str,
        run_id: str | None = None,
        generation: int | None = None,
):
    """Yield an accepted historical chain without materializing any tensor state."""
    from .acceptance import parent_acceptance_anchor_from_manifest

    root = Path(run_dir)
    manifest = manifest_sha256
    acceptance = acceptance_sha256
    bundle = load_historical_bamf_bundle(
        root / "bamf-bundles" / manifest,
        expected_manifest_sha256=manifest)
    if ((run_id is not None and bundle.run_id != run_id)
            or (generation is not None and bundle.generation != generation)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    binding = historical_accepted_binding_for_manifest(
        root, manifest, bundle,
        expected_acceptance_sha256=acceptance,
        expected_candidate_identity_sha256=None)
    while True:
        yield manifest, acceptance, bundle, binding
        if bundle.generation == 0:
            return
        parent_manifest = bundle.parent_manifest_sha256
        parent, parent_binding = load_historical_accepted_parent(
            root, manifest, bundle, binding)
        if parent is None or parent_binding is None or parent_manifest is None:
            return
        parent_acceptance = parent_acceptance_anchor_from_manifest(root, manifest)
        if parent_acceptance is None:
            return
        manifest, acceptance = parent_manifest, parent_acceptance
        bundle, binding = parent, parent_binding
