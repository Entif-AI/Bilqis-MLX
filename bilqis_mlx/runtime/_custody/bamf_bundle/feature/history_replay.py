"""Private mechanics for explicit historical accepted-feature replay."""
from pathlib import Path

from ..atlas_admission import ParsedAtlasAdmissionBinding
from ..publication import _require_published_acceptance
from ..records import invalid
from .acceptance import (
    accepted_generation,
)
from .receipt import AcceptedGenerationFeatureReceipt
from .replay_support import feature_schema, feature_source


def replay_accepted_feature_context(
        run_dir: Path, manifest_sha256: str, student, *,
        expected_acceptance_sha256: str, authenticate_materialization,
        load_bundle, accepted_binding, parent_acceptance_anchor):
    """Walk accepted ancestry only for audit, migration, or legacy replay."""
    history = []
    current_sha = manifest_sha256
    current = student
    current_acceptance = expected_acceptance_sha256
    legacy_feature_tail = False

    while True:
        binding = None if legacy_feature_tail else accepted_binding(
            run_dir, current_sha, current,
            expected_acceptance_sha256=current_acceptance)
        history.append((current, binding))
        if current.generation == 0:
            break
        parent_sha = current.parent_manifest_sha256
        if parent_sha is None:
            invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
        parent = load_bundle(
            run_dir / "bamf-bundles" / parent_sha,
            expected_manifest_sha256=parent_sha)
        if (parent.run_id != current.run_id
                or parent.generation + 1 != current.generation):
            invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
        if not legacy_feature_tail:
            parent_acceptance = parent_acceptance_anchor(
                run_dir, current_sha)
            if parent_acceptance is None:
                legacy_feature_tail = True
            else:
                current_acceptance = parent_acceptance
        current_sha = parent_sha
        current = parent

    materialization = authenticate_materialization(history[-1][0])
    materialization_count = 1
    features = materialization.features
    predecessor = None
    construction_predecessor = None
    result_binding = history[0][1]
    if result_binding is None:
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    for child, child_binding in reversed(history[:-1]):
        parent = current
        predecessor = features
        if child.extents.factor_map_digest == parent.extents.factor_map_digest:
            if (child.extents.active_semantic_digest
                    != parent.extents.active_semantic_digest
                    and not isinstance(child_binding, ParsedAtlasAdmissionBinding)):
                invalid("BAMF_FEATURE_ACTIVE_SET_DRIFT")
            source = feature_source(child.compiler_features)
            if (child.compiler_features.get("factor_map_sha256") != features.digest
                    or source != feature_source(parent.compiler_features)
                    or feature_schema(child.compiler_features)
                    != feature_schema(parent.compiler_features)
                    or child.provenance.release_digest != features.semantic_release
                    or source["release_sha256"] != features.semantic_release
                    or source["atlas_bundle_id"] != features.atlas_bundle_id
                    or source["source_bundle_id"] != features.source_bundle_id):
                invalid("BAMF_FEATURE_SOURCE_REPLAY_MISMATCH")
        else:
            construction_predecessor = features
            materialization = authenticate_materialization(
                child, predecessor=features)
            materialization_count += 1
            features = materialization.features
            if features.predecessor_digest != predecessor.digest:
                invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
        current = child
    return (features, result_binding, predecessor, construction_predecessor,
            materialization, materialization_count)


def read_accepted_generation_feature_materialization(
        pointer_path: Path, *, authenticate_materialization, load_bundle,
        accepted_binding, parent_acceptance_anchor):
    """Replay one accepted generation and mint its historical feature receipt."""
    pointer, student = accepted_generation(pointer_path)
    current_binding = _require_published_acceptance(
        pointer_path.parent, pointer, student)
    (features, binding, predecessor_features, construction_predecessor,
     materialization, materialization_count) = replay_accepted_feature_context(
        pointer_path.parent, pointer["manifest_sha256"], student,
        expected_acceptance_sha256=pointer["acceptance_sha256"],
        authenticate_materialization=authenticate_materialization,
        load_bundle=load_bundle, accepted_binding=accepted_binding,
        parent_acceptance_anchor=parent_acceptance_anchor)
    if binding != current_binding:
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    predecessor = None if predecessor_features is None else predecessor_features.digest
    if student.generation == 0:
        if predecessor is not None or features.predecessor_digest is not None:
            invalid("BAMF_FEATURE_LINEAGE_DRIFT")
    elif predecessor is None:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    receipt = AcceptedGenerationFeatureReceipt(
        run_id=student.run_id,
        generation=student.generation,
        generation_manifest_sha256=pointer["manifest_sha256"],
        parent_generation_manifest_sha256=student.parent_manifest_sha256,
        semantic_release=features.semantic_release,
        active_set_sha256=student.extents.active_semantic_digest,
        feature_sha256=features.digest,
        predecessor_feature_sha256=predecessor,
        compiler_sha256=student.compiler_features["compiler_sha256"],
        implementation_sha256=student.implementation_sha256,
        acceptance_sha256=binding.digest,
        source_atlas_bundle_id=features.atlas_bundle_id,
        source_release_sha256=features.semantic_release,
        source_source_bundle_id=features.source_bundle_id,
    )
    return (receipt, features, predecessor_features, construction_predecessor,
            materialization, materialization_count)
