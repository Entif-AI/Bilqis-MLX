"""A02 compiler-sidecar rebinding for an admitted parameter extension."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from bilqis_mlx.factory import ExecutableFactoryRelease
from bilqis_mlx.runtime.state import _fingerprint

from ..records import BamfBundleCandidate, canonical, invalid, sha


_FACTORY_BOUND_FIELDS = frozenset({
    "compiler_sha256",
    "factory_release_sha256",
    "factory_semantic_catalog_sha256",
    "factory_semantic_graph_sha256",
    "factory_semantic_catalog",
    "factory_grade_ids",
})


def parameter_extension_inert_compiler_state(record) -> dict:
    """Return compiler authority that A02 must preserve across publication."""
    return {
        key: value for key, value in dict(record).items()
        if key not in _FACTORY_BOUND_FIELDS
    }


def _compiler_digest(release: ExecutableFactoryRelease, factor_map_sha256: str) -> str:
    return sha(canonical({
        "schema": "bilqis.mlx.bamf-initial-compiler/v1",
        "execution_plan_sha256": release.execution_plan.digest(),
        "factor_map_sha256": factor_map_sha256,
    }))


def verify_parameter_extension_compiler_state(compiler, release) -> None:
    """Require the accepted compiler sidecar to name the exact Factory successor."""
    if not isinstance(release, ExecutableFactoryRelease):
        invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
    graph = compiler.get("factory_semantic_catalog")
    factor_map_sha256 = compiler.get("factor_map_sha256")
    if (not isinstance(graph, dict)
            or not isinstance(factor_map_sha256, str)
            or compiler.get("factory_release_sha256") != release.release_sha256
            or compiler.get("factory_semantic_catalog_sha256")
               != release.semantic_catalog_sha256
            or compiler.get("factory_semantic_graph_sha256") != _fingerprint(graph)
            or compiler.get("factory_grade_ids")
               != [grade.grade_id for grade in release.execution_plan.grades]
            or compiler.get("compiler_sha256")
               != _compiler_digest(release, factor_map_sha256)):
        invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
    try:
        release.verify_semantic_catalog(graph)
    except (TypeError, ValueError):
        invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")


def bind_parameter_extension_compiler_state(
        candidate: BamfBundleCandidate,
        release: ExecutableFactoryRelease,
        graph: dict) -> BamfBundleCandidate:
    """Project only release-bound compiler fields onto the admitted A02 child."""
    if type(candidate) is not BamfBundleCandidate or not isinstance(graph, dict):
        invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
    try:
        release.verify_semantic_catalog(graph)
    except (TypeError, ValueError):
        invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
    compiler = dict(candidate.compiler_features)
    factor_map_sha256 = compiler.get("factor_map_sha256")
    if not isinstance(factor_map_sha256, str):
        invalid("BAMF_ATLAS_ACCEPTED_FACTORY_RELEASE_DRIFT")
    compiler.update({
        "compiler_sha256": _compiler_digest(release, factor_map_sha256),
        "factory_release_sha256": release.release_sha256,
        "factory_semantic_catalog_sha256": release.semantic_catalog_sha256,
        "factory_semantic_graph_sha256": _fingerprint(graph),
        "factory_semantic_catalog": deepcopy(graph),
        "factory_grade_ids": [grade.grade_id for grade in release.execution_plan.grades],
    })
    verify_parameter_extension_compiler_state(compiler, release)
    return replace(candidate, compiler_features=compiler)
