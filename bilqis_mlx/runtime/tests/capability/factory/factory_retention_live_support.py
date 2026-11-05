"""Real-source/A01 support for the positive Factory-owned C05 witness."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import mlx.core as mx

from bilqis_mlx.boolean_composite import build_course as build_composite
from bilqis_mlx.boolean_identification import build_course as build_identification
from bilqis_mlx.compatibility.executable_projection import project_legacy_course
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
    fixed_domain, merge_prefix_domain,
)
from bilqis_mlx.factory.executable_release import (
    compile_executable_factory_release, compile_successor_profile_release,
)
from bilqis_mlx.factory.live_releases import (
    boolean_successor, initial_course, minimal_boolean_successor,
)
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.profiles.catalog import numeric_entry_transition
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationProvenance, Initializer, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE
from bilqis_mlx.source_adapters.school import live_source_registry


HP = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)


def live_factory_context(root: Path, source: Path):
    """Compile the current admitted A/B/C Factory release from pinned source."""
    manifest = json.loads((
        root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
    grade_a = initial_course(accepted_grade_a(manifest))
    course = boolean_successor(grade_a, source)
    course = build_composite(course, source)
    course = build_identification(course, source)
    grade_b = replace(
        course.grades[-1],
        teaching_stages=(
            tuple(cap.id for cap in course.grades[-1].capabilities[:6]),
            ("B.COMPOSITE",), ("B.IDBOOLOPS",),
        ))
    course = replace(course, grades=(course.grades[0], grade_b))
    registered = registry_graph()
    graph = {
        **registered,
        "tokens": registered["tokens"][:HISTORICAL_PREFIX_SIZE],
        "nodes": registered["nodes"][:HISTORICAL_PREFIX_SIZE],
        "row_contract_sha256": {
            key: registered["row_contract_sha256"][key]
            for key in registered["tokens"][:HISTORICAL_PREFIX_SIZE]
        },
    }
    sources = live_source_registry()
    answers = AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/v1", "a" * 64),
            fixed_domain(("FALSE", "TRUE")),
            lambda value: {"FALSE": "cogal.value.false",
                           "TRUE": "cogal.value.true"}[value]),
        RegisteredAnswerModality(
            AnswerModality(
                "boolean_operator", "answer.boolean-operator/v1", "b" * 64),
            fixed_domain(("NOT", "AND", "OR", "XOR", "IMPLIES", "IFF")),
            lambda value: "cogal.operator." + value),
        RegisteredAnswerModality(
            AnswerModality("numeric_active", "answer.numeric-active/v1", "c" * 64),
            merge_prefix_domain, lambda value: "school.number." + value),
    ))
    historical = minimal_boolean_successor(grade_a, source)
    curriculum, bindings, profile, _ = project_legacy_course(
        historical, grade_a, source, answer_kinds=answers.kinds)
    projected = compile_executable_factory_release(
        curriculum, bindings, profile, sources, answers,
        source_root=source, graph=graph, verification_seed=2026101904)
    transition = numeric_entry_transition(projected, graph, full_boolean=False)
    release = compile_successor_profile_release(
        projected, transition.profile, sources, answers,
        source_root=source, graph=transition.graph, verification_seed=2026101905)
    from bilqis_mlx.runtime.source_execution import SourceExecutionContext
    return SourceExecutionContext(
        release, transition.graph, source, sources, answers), manifest


def genesis_bundle(base, snapshot, schema):
    """Build full-topology generation zero from the real A01 parameter surface."""
    allocations = MotifAllocationSnapshot(MotifManifest(snapshot.release_sha256))
    extents = replace(
        base.compiled.extents,
        motif_key_map_digest=allocations.manifest.digest,
    )
    declared = expected_bamf_shapes(ModelTopologySpecV2(), extents)
    parameters = {
        item.name: (base.parameters[item.name]
                    if base.parameters[item.name].shape == item.shape
                    else mx.zeros(item.shape, dtype=mx.float32))
        for item in declared
    }
    rowwise = {Initializer.IDENTITY_BANK, Initializer.MOTIF_PAGE,
               Initializer.FEATURE_TABLE}
    counts = {
        item.name: mx.zeros(
            (item.shape[0],) if (
                item.initializer in rowwise
                or (item.initializer is Initializer.EMBEDDING and len(item.shape) == 2)
            ) else (), dtype=mx.uint64)
        for item in declared
    }
    optimizer = AdamWStateTree(
        parameters,
        {name: mx.zeros_like(value) for name, value in parameters.items()},
        {name: mx.zeros_like(value) for name, value in parameters.items()},
        counts)
    state = CandidateState(
        optimizer, PlasticityPolicy("FOUNDATION", 0, ()), allocations, 0)
    compiler_features = {
        "schema": "bilqis.mlx.bamf-compiler-features/v1",
        "factor_map_sha256": extents.factor_map_digest,
        "compiler_sha256": "f" * 64,
        "rights_epoch": 1,
        "correction_generation": 1,
        "feature_source": {
            "atlas_bundle_id": snapshot.bundle_id,
            "release_sha256": snapshot.release_sha256,
            "source_bundle_id": snapshot.source_bundle_id,
        },
        "feature_schema": {
            "role_ids": list(schema.role_ids),
            "schema_ids": list(schema.schema_ids),
            "source_bindings": [list(item) for item in schema.source_bindings],
        },
    }
    bundle = BamfBundleCandidate(
        "factory-c05-live", 0, None, "e" * 64, ModelTopologySpecV2(), extents,
        state, HP,
        GenerationProvenance(
            "factory-c05-source", snapshot.release_sha256, "factory-c05-teacher", 1),
        {"schema": "bilqis.mlx.bamf-semantic-abi/v1",
         "active_set_sha256": snapshot.active_set_sha256,
         "semantic_bank_count": extents.semantic_bank_count,
         "bank_identities": [f"bank:{index}"
                             for index in range(extents.semantic_bank_count)]},
        compiler_features,
        {"schema": "bilqis.mlx.bamf-correction-frontier/v1",
         "source_identity": "factory-c05-source",
         "release_digest": snapshot.release_sha256,
         "rights_epoch": 1, "correction_generation": 1, "frontier": []},
        {"schema": "bilqis.mlx.bamf-teacher-state/v1",
         "teacher_identity": "factory-c05-teacher", "teacher_epoch": 1,
         "next_seed": 1, "cursor": "c05"},
        {"schema": "bilqis.mlx.bamf-evaluation-contract/v1",
         "contract_sha256": "9" * 64},
        {"schema": "bilqis.mlx.bamf-generation-transition/v1", "kind": "INITIAL",
         "invalidate_derived_caches": False},
        ({"event": "FACTORY_C05_GENESIS", "optimizer_step": 0},),
    )
    return bundle, declared


__all__ = ("HP", "genesis_bundle", "live_factory_context")
