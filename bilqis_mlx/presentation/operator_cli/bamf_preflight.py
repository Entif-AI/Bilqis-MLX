"""Read-only BAMF configuration inspection, without admission or learner custody."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2


def reject_manifest_request(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_ATLAS_ADMISSION.INVALID, reason=reason)


@dataclass(frozen=True)
class ManifestReference:
    path: str
    sha256: str
    qualification: str = 'NOT_VERIFIED'


@dataclass(frozen=True)
class BamfPreflight:
    model_topology: ModelTopologySpecV2
    run_dir: str
    resume: bool
    admission_policy: str
    atlas_release_manifest: ManifestReference | None
    source_prefetch_workers: int
    retention_enabled: bool
    human_run: bool
    schema: str = 'bilqis.bamf.operator-preflight/v1'
    result: str = 'HELD_PENDING_SOURCE_AND_GENERATION_AUTHORITY'
    ready_for_training: bool = False
    neural_updates: int = 0

    def to_record(self) -> dict:
        record = asdict(self)
        record['model_topology'] = self.model_topology.to_record()
        return record


def _manifest_reference(args) -> ManifestReference | None:
    path = args.atlas_release_manifest
    if args.admission_policy == 'staged':
        if path is not None:
            reject_manifest_request('release-manifest-requires-atlas-release-policy')
        return None
    if path is None:
        reject_manifest_request('atlas-release-manifest-required')
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_file():
        reject_manifest_request('atlas-release-manifest-file-invalid')
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    return ManifestReference(str(path.absolute()), digest)


def bamf_preflight(args, topology: ModelTopologySpecV2) -> BamfPreflight:
    """Inspect requested configuration; never read checkpoint arrays or claim approval."""
    if args.atlas_admission_scope is not None:
        reject_manifest_request('lease-scope-not-accepted-by-configuration-inspection')
    manifest = _manifest_reference(args)
    run_dir = args.run_dir.expanduser()
    legacy = run_dir / 'state.json'
    pointer = run_dir / 'bamf-state.json'
    if legacy.exists() or legacy.is_symlink():
        reject_manifest_request('legacy-lineage-cannot-be-coerced-to-bamf')
    if pointer.exists() or pointer.is_symlink():
        if not args.resume:
            reject_manifest_request('existing-bamf-lineage-requires-resume')
    elif args.resume:
        reject_manifest_request('bamf-resume-pointer-unavailable')
    return BamfPreflight(
        topology, str(run_dir.absolute()), args.resume, args.admission_policy,
        manifest, args.source_prefetch_workers, not args.no_retention, args.human_run)
