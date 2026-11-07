"""Compile successors, admit releases, and reconstruct answer heads."""
from __future__ import annotations

from ..adapters import SourceAdapterRegistry
from ..answers import AnswerModalityRegistry
from ..execution import CurriculumProfile
from .primitives import ExecutableAdmissionReceipt
from .release import ExecutableFactoryRelease

from .. import executable_release as _api


def compile_successor_profile_release(
        predecessor: ExecutableFactoryRelease,
        profile: CurriculumProfile,
        source_registry: SourceAdapterRegistry,
        answer_registry: AnswerModalityRegistry, *,
        source_root, graph: dict, verification_seed: int) -> ExecutableFactoryRelease:
    """Recompile one profile over the predecessor's immutable authorities."""
    if not isinstance(predecessor, _api.ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_INVALID")
    predecessor.verify()
    return _api.compile_executable_factory_release(
        predecessor.curriculum,
        predecessor.source_bindings,
        profile,
        source_registry,
        answer_registry,
        source_root=source_root,
        graph=graph,
        verification_seed=verification_seed,
        predecessor=predecessor,
    )


def admit_executable_factory_release(
        release: ExecutableFactoryRelease, *, student_sha256: str,
        optimizer_step: int, semantic_graph_sha256: str,
        graph: dict) -> ExecutableAdmissionReceipt:
    """Bind one verified v2 release to an exact causal-student baseline."""
    if not isinstance(release, _api.ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_ADMISSION_RELEASE_REQUIRED")
    release.verify()
    release.verify_semantic_catalog(graph)
    receipt = _api.ExecutableAdmissionReceipt(
        factory_release_sha256=release.release_sha256,
        execution_plan_sha256=release.execution_plan.digest(),
        curriculum_sha256=release.curriculum.digest(),
        source_binding_sha256=release.source_bindings.digest(),
        semantic_catalog_sha256=release.semantic_catalog_sha256,
        semantic_graph_sha256=semantic_graph_sha256,
        student_sha256=student_sha256,
        optimizer_step=optimizer_step,
    )
    receipt.verify(release)
    return receipt


def answer_heads_from_executable_release(
        release: ExecutableFactoryRelease, graph: dict) -> dict:
    """Return the admitted typed readout without grade/release reconstruction."""
    if not isinstance(release, _api.ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_RELEASE_REQUIRED")
    release.verify()
    release.verify_semantic_catalog(graph)
    names = graph["tokens"]
    result = {
        "semantic_token": {
            "values": list(names),
            "token_ids": list(range(len(names))),
        },
    }
    modalities = {
        modality.kind: modality for modality in release.answer_modalities
    }
    for head in release.answer_heads:
        modality = modalities[head.kind]
        result[head.kind] = {
            "values": list(head.values),
            "token_ids": list(head.token_ids),
            "modality_id": modality.adapter_id,
            "implementation_sha256": modality.implementation_sha256,
        }
    return result


def _prepare_predecessor_transition(predecessor, plan, semantic_catalog, lineage):
    """Verify predecessor custody and derive the exact semantic transition."""
    predecessor_sha = None
    transition = None
    if predecessor is not None:
        if not isinstance(predecessor, _api.ExecutableFactoryRelease):
            raise TypeError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_INVALID")
        predecessor.verify()
        derived_lineage = _api.PlanLineage.from_semantic_catalogs(
            predecessor.execution_plan, plan,
            predecessor.semantic_catalog, semantic_catalog)
        if lineage is not None and lineage != derived_lineage:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_LINEAGE_DRIFT")
        lineage = derived_lineage
        transition = _api.diff_execution_plans(
            predecessor.execution_plan, plan, lineage=lineage)
        if transition.semantic_geometry == _api.SemanticGeometryChange.INCOMPATIBLE.value:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_INCOMPATIBLE_GEOMETRY")
        predecessor_sha = predecessor.release_sha256
    elif lineage is not None:
        raise ValueError("FACTORY_EXECUTABLE_RELEASE_LINEAGE_WITHOUT_PREDECESSOR")

    return predecessor_sha, transition
