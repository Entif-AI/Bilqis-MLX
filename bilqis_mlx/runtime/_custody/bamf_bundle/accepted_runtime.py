"""Accepted-generation runtime custody for B08/B14/C09 live execution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest

from .codec import load_bamf_bundle
from .execution_cache import _issue_accepted_execution_cache, bind_cache_authority
from .publication import (
    _live_bundle_manifest, _pointer_lock, _read_pointer,
    _require_published_acceptance,
)
from .records import (
    BAMF_POINTER_SCHEMA, CompleteStudent, canonical, invalid, sha, sidecar_records,
)


class _ExecutionCacheOwner:
    """Process-lifetime custody for one retained execution cache per live run."""

    def __init__(self):
        self.lock = RLock()
        self.entries = {}

    def get(self, key):
        return self.entries.get(key)

    def set(self, key, manifest_sha256, cache) -> None:
        self.entries[key] = (manifest_sha256, cache)


_EXECUTION_CACHE_OWNER = _ExecutionCacheOwner()


@dataclass(frozen=True)
class AcceptedGenerationIdentity:
    """The published identity of the accepted generation in custody."""

    run_id: str
    generation: int
    manifest_sha256: str
    topology_digest: str
    extents_digest: str
    optimizer_step: int
    candidate_identity_sha256: str


def _read_accepted(run_dir: Path):
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    with _pointer_lock(run_dir):
        pointer = _read_pointer(pointer_path)
        if pointer is None:
            invalid("BAMF_GENERATION_POINTER_MISSING")
        student = load_bamf_bundle(
            run_dir / "bamf-bundles" / pointer["manifest_sha256"],
            expected_manifest_sha256=pointer["manifest_sha256"])
        if (student.run_id != pointer["run_id"]
                or student.generation != pointer["generation"]
                or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
            invalid("BAMF_GENERATION_POINTER_DRIFT")
        _require_published_acceptance(run_dir, pointer, student)
    return pointer, student


def load_accepted_generation(run_dir: Path) -> CompleteStudent:
    """Load the currently published accepted generation under the pointer lock."""
    return _read_accepted(run_dir)[1]


def _identity_from_pointer(
        student: CompleteStudent, pointer: dict) -> AcceptedGenerationIdentity:
    manifest = pointer.get("manifest_sha256") if isinstance(pointer, dict) else None
    if (type(student) is not CompleteStudent
            or not isinstance(pointer, dict)
            or pointer.get("schema") != BAMF_POINTER_SCHEMA
            or pointer.get("run_id") != student.run_id
            or pointer.get("generation") != student.generation
            or pointer.get("parent_manifest_sha256") != student.parent_manifest_sha256
            or not isinstance(manifest, str) or len(manifest) != SHA256_HEX_LENGTH
            or any(char not in "0123456789abcdef" for char in manifest)):
        invalid("BAMF_GENERATION_POINTER_DRIFT")
    return AcceptedGenerationIdentity(
        run_id=student.run_id,
        generation=student.generation,
        manifest_sha256=manifest,
        topology_digest=student.topology.digest,
        extents_digest=student.extents.digest,
        optimizer_step=student.retained_state.optimizer_step,
        candidate_identity_sha256=candidate_identity_digest(student.retained_state))


def _published_in_memory_identity(
        run_dir: Path, student: CompleteStudent) -> AcceptedGenerationIdentity:
    run_dir = Path(run_dir)
    if type(student) is not CompleteStudent:
        invalid("BAMF_GENERATION_POINTER_DRIFT")
    with _pointer_lock(run_dir):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        if pointer is None:
            invalid("BAMF_GENERATION_POINTER_MISSING")
        identity = _identity_from_pointer(student, pointer)
        manifest = _live_bundle_manifest(run_dir, pointer)
        if (manifest["implementation_sha256"] != student.implementation_sha256
                or canonical(manifest["topology"])
                != canonical(student.topology.to_record())
                or canonical(manifest["extents"])
                != canonical(student.extents.to_record())
                or canonical(manifest["provenance"])
                != canonical(student.provenance.to_record())
                or canonical(manifest["transition"])
                != canonical(dict(student.transition))
                or manifest["optimizer"]["step"] != student.retained_state.optimizer_step
                or canonical(manifest["optimizer"]["hyperparameters"])
                != canonical(asdict(student.optimizer_hyperparameters))):
            invalid("BAMF_GENERATION_POINTER_DRIFT")
        for name, record in sidecar_records(student).items():
            stored = manifest["sidecars"].get(name)
            if (not isinstance(stored, dict)
                    or stored.get("sha256") != sha(canonical(record))):
                invalid("BAMF_GENERATION_POINTER_DRIFT")
        _require_published_acceptance(run_dir, pointer, student)
    return identity


def bind_accepted_execution_cache(run_dir: Path):
    """Authenticate the live accepted generation and mint its retained B08 cache."""
    run_dir = Path(run_dir)
    _pointer, student = _read_accepted(run_dir)
    identity = _published_in_memory_identity(run_dir, student)
    generation_binding = execution_generation_digest(
        student.retained_state.optimizer.parameters,
        spec=student.topology,
        extents=student.extents,
    )
    key = str(run_dir.resolve())
    with _EXECUTION_CACHE_OWNER.lock:
        retained = _EXECUTION_CACHE_OWNER.get(key)
        if retained is not None and retained[0] == identity.manifest_sha256:
            cache = retained[1]
            if (cache.run_id != identity.run_id
                    or cache.generation != identity.generation
                    or cache.generation_binding != generation_binding
                    or cache.motif_manifest.digest
                    != student.retained_state.allocations.manifest.digest):
                invalid("BAMF_EXECUTION_CACHE_CUSTODY_DRIFT")
            if cache._run_dir is None:
                object.__setattr__(cache, "_run_dir", run_dir.resolve())
            return cache
        cache = _issue_accepted_execution_cache(
            run_id=identity.run_id,
            generation=identity.generation,
            accepted_manifest_sha256=identity.manifest_sha256,
            generation_binding=generation_binding,
            motif_manifest=student.retained_state.allocations.manifest,
        )
        _EXECUTION_CACHE_OWNER.set(key, identity.manifest_sha256, cache)
        object.__setattr__(cache, "_run_dir", run_dir.resolve())
        return cache


def bind_accepted_cache_authority(
    run_dir: Path, registry, eligibility_source=None,
):
    """Issue/reuse the B14 authority owned by the current accepted generation."""
    cache = bind_accepted_execution_cache(run_dir)
    return cache, bind_cache_authority(cache, registry, eligibility_source)


def bind_accepted_correction_authority(run_dir: Path, registry):
    """Re-establish host C09 verification authority for an accepted cold start."""
    from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry
    from bilqis_mlx.runtime.accepted_corrections import bind_accepted_registry

    if not isinstance(registry, SourceAuthorityRegistry):
        invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
    cache = bind_accepted_execution_cache(run_dir)
    if (cache._correction_registry is not None
            and cache._correction_registry != registry):
        invalid("BAMF_C09_CORRECTION_AUTHORITY_DRIFT")
    object.__setattr__(cache, "_correction_registry", registry)
    bind_accepted_registry(
        Path(run_dir), cache.accepted_manifest_sha256, registry)
    return cache


def interactive_accepted_cache_inference(
    run_dir: Path, registry, artifact, expected_binding, *,
    cached_infer, fp32_recompute, quality_check, policy,
    eligibility_source=None,
):
    """Read B14 cache only through the authority owned by accepted B13 custody."""
    from bilqis_mlx.runtime.atlas_cache_codec import interactive_cache_inference

    _cache, authority = bind_accepted_cache_authority(
        run_dir, registry, eligibility_source)
    return interactive_cache_inference(
        authority, artifact, expected_binding,
        cached_infer=cached_infer,
        fp32_recompute=fp32_recompute,
        quality_check=quality_check,
        policy=policy,
    )


__all__ = (
    "AcceptedGenerationIdentity", "_EXECUTION_CACHE_OWNER",
    "_identity_from_pointer", "_published_in_memory_identity", "_read_accepted",
    "bind_accepted_cache_authority", "bind_accepted_correction_authority",
    "bind_accepted_execution_cache", "interactive_accepted_cache_inference",
    "load_accepted_generation",
)
