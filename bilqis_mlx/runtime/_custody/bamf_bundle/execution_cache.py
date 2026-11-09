"""B13-issued retained cache authority consumed by the B11 forward owner."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import weakref

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import MotifManifest


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


@dataclass(frozen=True, init=False)
class AcceptedExecutionCache:
    """A motif manifest authenticated against one accepted B13 generation."""

    run_id: str
    generation: int
    accepted_manifest_sha256: str
    generation_binding: str
    motif_manifest: MotifManifest
    source_authority_registry_sha256: str | None
    schema_version: str = "bilqis.mlx.b13-accepted-execution-cache/v1"
    _motif_artifact_owners: dict = field(init=False, repr=False, compare=False)
    _run_dir: Path | None = field(init=False, repr=False, compare=False)
    _correction_registry: object | None = field(init=False, repr=False, compare=False)
    _source_authority: object | None = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B13_EXECUTION_CACHE_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        if (
            not isinstance(self.run_id, str) or not self.run_id
            or type(self.generation) is not int or self.generation < 0
            or not _digest(self.accepted_manifest_sha256)
            or not _digest(self.generation_binding)
            or type(self.motif_manifest) is not MotifManifest
            or (self.source_authority_registry_sha256 is not None
                and not _digest(self.source_authority_registry_sha256))
            or self.schema_version
            != "bilqis.mlx.b13-accepted-execution-cache/v1"
        ):
            _invalid("B13_EXECUTION_CACHE_INVALID")


def _new_execution_cache(
    *,
    run_id: str,
    generation: int,
    accepted_manifest_sha256: str,
    generation_binding: str,
    motif_manifest: MotifManifest,
    source_authority_registry_sha256: str | None = None,
) -> AcceptedExecutionCache:
    cache = object.__new__(AcceptedExecutionCache)
    for name, value in (
        ("run_id", run_id),
        ("generation", generation),
        ("accepted_manifest_sha256", accepted_manifest_sha256),
        ("generation_binding", generation_binding),
        ("motif_manifest", motif_manifest),
        ("source_authority_registry_sha256", source_authority_registry_sha256),
        ("schema_version", "bilqis.mlx.b13-accepted-execution-cache/v1"),
        ("_motif_artifact_owners", weakref.WeakValueDictionary()),
        ("_run_dir", None),
        ("_correction_registry", None),
        ("_source_authority", None),
    ):
        object.__setattr__(cache, name, value)
    cache.__post_init__()
    return cache


def require_accepted_execution_cache(cache) -> AcceptedExecutionCache:
    if type(cache) is not AcceptedExecutionCache:
        _invalid("B13_EXECUTION_CACHE_REQUIRED")
    cache.__post_init__()
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        _require_owned_execution_cache,
    )
    return _require_owned_execution_cache(cache)


def bind_motif_artifact_owner(cache, compiled):
    """Bind mutable C09 hold state to one immutable compiled-frame identity."""
    cache = require_accepted_execution_cache(cache)
    from bilqis_mlx.runtime.atlas_motif_owner import MotifArtifactOwner
    key = compiled.packed_frame_artifact_owner.cache_identity
    owner = cache._motif_artifact_owners.get(key)
    if owner is None:
        owner = MotifArtifactOwner(cache, compiled)
        cache._motif_artifact_owners[key] = owner
    if cache._run_dir is not None:
        from bilqis_mlx.runtime.accepted_corrections import (
            register_accepted_target,
        )
        register_accepted_target(
            cache._run_dir, cache.accepted_manifest_sha256,
            "MOTIF", owner,
        )
    owner.require(cache, compiled)
    return owner


__all__ = (
    "AcceptedExecutionCache", "bind_motif_artifact_owner",
    "require_accepted_execution_cache",
)
