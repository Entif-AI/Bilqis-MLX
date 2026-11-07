"""Production C09 correction ingress for stateful artifact owners."""
from __future__ import annotations

from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent
from .atlas_source_authority import SourceAuthorityRegistry


def _route(owner, event, authority_registry) -> bool:
    if (not isinstance(event, CorrectionEvent)
            or not isinstance(authority_registry, SourceAuthorityRegistry)
            or not hasattr(owner, "index")
            or not hasattr(owner, "apply_correction")):
        _invalid("BAMF_C09_OWNER_INGRESS_INVALID")
    authority_registry.verify_correction(event)
    if not owner.index.direct_dependents(event.dependency):
        return False
    owner.apply_correction(event, authority_registry)
    return True


def apply_compiled_batch_correction(batch, event, authority_registry) -> tuple[str, ...]:
    """Route one signed correction into the B11/A05 owners used by this batch."""
    from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch
    if type(batch) is not BamfCompiledBatch:
        _invalid("BAMF_C09_COMPILED_BATCH_OWNER_REQUIRED")
    batch.__post_init__()
    affected = []
    if _route(batch.atlas_feature_artifact_owner, event, authority_registry):
        affected.append("ATLAS_FEATURE")
    packed_owner = batch.compiled.packed_frame_artifact_owner
    if _route(packed_owner, event, authority_registry):
        affected.append("PACKED_FRAME")
    return tuple(affected)


def apply_motif_correction(cache, compiled, event, authority_registry) -> bool:
    """Route one signed correction into the B13 retained-motif owner."""
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import bind_motif_artifact_owner
    owner = bind_motif_artifact_owner(cache, compiled)
    return _route(owner, event, authority_registry)


def apply_solve_context_correction(context, event, authority_registry) -> bool:
    """Route one signed correction into qualified C04 composition custody."""
    from bilqis_mlx.runtime.cognitive_solver import SolveContext
    if type(context) is not SolveContext:
        _invalid("BAMF_C09_SOLVE_CONTEXT_OWNER_REQUIRED")
    context.__post_init__()
    return _route(
        context.operator_composition_artifact_owner, event, authority_registry)


def apply_capability_support_correction(owner, event, authority_registry) -> bool:
    """Route one signed correction into accepted learned-support custody."""
    from .atlas_capability_support_owner import CapabilitySupportArtifactOwner
    if not isinstance(owner, CapabilitySupportArtifactOwner):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_REQUIRED")
    return _route(owner, event, authority_registry)


__all__ = (
    "apply_capability_support_correction",
    "apply_compiled_batch_correction",
    "apply_motif_correction",
    "apply_solve_context_correction",
)
