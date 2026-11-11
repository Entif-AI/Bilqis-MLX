"""B13 generation-zero run identity, construction, and bootstrap authority."""
from __future__ import annotations

from bilqis_mlx.runtime.atlas_optimizer import _create_unbound_bamf_optimizer

from .foundation import (
    InitialFoundationFeatureAuthority, issue_initial_foundation_feature_authority,
)
from .origin import (
    InitialFactoryFoundationAuthority, issue_initial_factory_foundation_authority,
)
from .preparation import (
    prepare_initial_generation, validate_initial_generation_binding,
    validate_initial_generation_preparation, validate_parsed_initial_generation_binding,
)
from .preparation_authority import (
    PreparedInitialGeneration, _issue_binding,
    validate_initial_generation_source_authority,
)
from .records import (
    BamfRunIdentity, InitialGenerationBinding, ParsedInitialGenerationBinding,
)


def publish_initial_generation(run_dir, prepared: PreparedInitialGeneration, *, reserve_gib=100.0):
    """Publish genesis through the existing B13 transaction, never through C05."""
    from ..publication import _publish_authorized_generation
    return _publish_authorized_generation(
        run_dir, prepared.candidate, prepared, reserve_gib=reserve_gib)


def recover_prepared_initial_generation(run_dir, prepared: PreparedInitialGeneration):
    from ..publication import recover_prepared_initial_generation as recover
    return recover(run_dir, prepared)


def recover_sealed_initial_generation(run_dir, **expectations):
    from ..publication import recover_sealed_initial_generation as recover
    return recover(run_dir, **expectations)


__all__ = (
    "BamfRunIdentity", "InitialGenerationBinding", "ParsedInitialGenerationBinding",
    "PreparedInitialGeneration", "InitialFoundationFeatureAuthority",
    "issue_initial_foundation_feature_authority", "InitialFactoryFoundationAuthority",
    "issue_initial_factory_foundation_authority", "prepare_initial_generation",
    "publish_initial_generation", "validate_initial_generation_binding",
    "recover_prepared_initial_generation", "recover_sealed_initial_generation",
    "validate_initial_generation_preparation", "validate_parsed_initial_generation_binding",
    "validate_initial_generation_source_authority",
)
