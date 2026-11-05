"""Authority for source-owned partial forests."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.partial_visible_forest")
from ..context_eligibility import (
    ContextEligibility, ContextHold, check_context_eligibility,
)
from ..frame_compiler import FrameCompilerConfig, _invalid


def _validate_hidden_parent_current_authority(
    envelope: ContextEligibility,
    compiler_config: FrameCompilerConfig,
) -> None:
    """Recheck hidden source authority against the live A13 frontier.

    This consumes the hidden envelope only as validation input. The resulting
    A13 projection, member evidence, and member handles never enter the p4
    receipt or compiler cache identity.
    """
    current = _public().check_context_eligibility(
        (envelope,),
        compiler_config.task,
        compiler_config.frontier,
        compiler_config.policy,
    )
    if isinstance(current, ContextHold):
        _public()._invalid("BAMF_PREFIX_PARTIAL_SOURCE_AUTHORITY_INVALID")
