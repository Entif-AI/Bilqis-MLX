"""Admission and typed answer readout for verified executable releases."""
from __future__ import annotations
from .records import ExecutableAdmissionReceipt
from .release import ExecutableFactoryRelease

def admit_executable_factory_release(
        release: ExecutableFactoryRelease, *, student_sha256: str,
        optimizer_step: int, semantic_graph_sha256: str,
        graph: dict) -> ExecutableAdmissionReceipt:
    """Bind one verified v2 release to an exact causal-student baseline."""
    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_ADMISSION_RELEASE_REQUIRED")
    release.verify()
    release.verify_semantic_catalog(graph)
    receipt = ExecutableAdmissionReceipt(
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
    if not isinstance(release, ExecutableFactoryRelease):
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

