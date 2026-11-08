"""Independent host custody for the C09 source-authority trust root."""
from __future__ import annotations

import json
from pathlib import Path

from .records import invalid


SOURCE_AUTHORITY_REGISTRY_FILE = "source-authority-registry.json"
_MAX_REGISTRY_BYTES = 256 * 1024


def read_provisioned_source_authority_registry(run_dir: Path):
    """Read trusted registry material provisioned outside generation publication."""
    path = Path(run_dir) / SOURCE_AUTHORITY_REGISTRY_FILE
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    try:
        raw = path.read_bytes()
    except OSError:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    if not raw or len(raw) > _MAX_REGISTRY_BYTES:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
    return SourceAuthorityRegistry.from_record(record)


def require_provisioned_source_authority_registry(
        run_dir: Path, correction_frontier):
    """Bind candidate/live C09 material to an independent host-provisioned root."""
    trusted = read_provisioned_source_authority_registry(run_dir)
    record = correction_frontier.get("source_authority_registry")
    digest = correction_frontier.get("source_authority_registry_sha256")
    if trusted is None:
        if record is not None or digest is not None:
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED")
        return None
    if record is None or digest is None:
        invalid("BAMF_C09_SOURCE_AUTHORITY_BINDING_REQUIRED")
    from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
    candidate = SourceAuthorityRegistry.from_record(record)
    if candidate.digest != digest or candidate != trusted:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH")
    return trusted


__all__ = (
    "SOURCE_AUTHORITY_REGISTRY_FILE",
    "read_provisioned_source_authority_registry",
    "require_provisioned_source_authority_registry",
)
