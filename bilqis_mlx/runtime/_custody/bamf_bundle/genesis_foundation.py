"""Owner-derived sidecars for a fresh BAMF generation-zero foundation."""
from __future__ import annotations

from bilqis_mlx.factory.executable_release import (
    ExecutableAdmissionReceipt, ExecutableFactoryRelease,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.state import _fingerprint

from .records import canonical, invalid, sha


def _verified_factory(release, admission, graph) -> None:
    if (type(release) is not ExecutableFactoryRelease
            or type(admission) is not ExecutableAdmissionReceipt
            or not isinstance(graph, dict)):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    try:
        release.verify()
        release.verify_semantic_catalog(graph)
        admission.verify(release)
    except (TypeError, ValueError):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    if admission.semantic_graph_sha256 != _fingerprint(graph):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")


def initial_foundation_sidecars(
        release: ExecutableFactoryRelease,
        admission: ExecutableAdmissionReceipt,
        graph: dict, *, run_seed: int) -> tuple[dict, dict, dict, dict, dict]:
    """Project genesis sidecars only from independently admitted Factory state.

    Generation zero has no accepted correction or C03 visit history yet.  B13
    therefore records the canonical fresh-run baseline instead of accepting a
    caller's JSON description of that baseline.  Later owners may advance these
    records only through accepted successor generations.
    """
    _verified_factory(release, admission, graph)
    if type(run_seed) is not int or run_seed < 0:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")

    plan = release.execution_plan
    projections = plan.projection_digests
    rows = ModelTopologySpecV2.semantic_bank_rows
    bank_count = max(1, (len(release.semantic_catalog) + rows - 1) // rows)
    semantic = {
        "schema": "bilqis.mlx.bamf-semantic-abi/v1",
        "active_set_sha256": release.semantic_catalog_sha256,
        "semantic_bank_count": bank_count,
        "bank_identities": [f"bank:{index}" for index in range(bank_count)],
    }
    factor_map_sha256 = sha(canonical({
        "schema": "bilqis.mlx.bamf-initial-factor-map/v1",
        "semantic_catalog_sha256": release.semantic_catalog_sha256,
        "source_projection_sha256": projections.source,
        "answer_schema_projection_sha256": projections.answer_schema,
    }))
    compiler = {
        "schema": "bilqis.mlx.bamf-compiler-features/v1",
        "factor_map_sha256": factor_map_sha256,
        "compiler_sha256": sha(canonical({
            "schema": "bilqis.mlx.bamf-initial-compiler/v1",
            "execution_plan_sha256": plan.digest(),
            "factor_map_sha256": factor_map_sha256,
        })),
        "rights_epoch": 0,
        "correction_generation": 0,
    }
    source_identity = (release.source_bindings.source_attestation_sha256
                       or release.source_bindings.digest())
    correction = {
        "schema": "bilqis.mlx.bamf-correction-frontier/v1",
        "source_identity": source_identity,
        "release_digest": release.release_sha256,
        "rights_epoch": 0,
        "correction_generation": 0,
        "frontier": [],
    }
    teacher = {
        "schema": "bilqis.mlx.bamf-teacher-state/v1",
        "teacher_identity": projections.teaching,
        "teacher_epoch": 0,
        "next_seed": run_seed,
        "cursor": "GENESIS",
    }
    evaluation = {
        "schema": "bilqis.mlx.bamf-evaluation-contract/v1",
        "contract_sha256": projections.assessment,
    }
    return semantic, compiler, correction, teacher, evaluation


__all__ = ("initial_foundation_sidecars",)
