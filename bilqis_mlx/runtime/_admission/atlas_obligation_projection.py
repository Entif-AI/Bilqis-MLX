"""Restart-durable projection of accepted Atlas obligation credit ancestry."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.runtime.state import _durable_json


_SCHEMA = "bilqis.bamf.accepted-obligation-projection/v1"


def _memo_path(run_dir: Path) -> Path:
    return Path(run_dir) / "bamf-planning-derived" / "accepted-obligation-credit.json"


def _valid_keys(value) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, list) and len(item) == 2 for item in value)
        and all(isinstance(item[0], str) and item[0] for item in value)
        and all(
            isinstance(item[1], str) and len(item[1]) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in item[1])
            for item in value)
        and tuple(tuple(item) for item in value)
            == tuple(sorted({tuple(item) for item in value}))
    )


def _record(run_dir: Path):
    path = _memo_path(run_dir)
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    expected = {
        "schema", "run_id", "factory_release_sha256", "obligation_keys",
        "validated_checkpoint_sha256",
    }
    if (not isinstance(value, dict) or set(value) != expected
            or value.get("schema") != _SCHEMA
            or not isinstance(value.get("run_id"), str)
            or not isinstance(value.get("factory_release_sha256"), str)
            or len(value["factory_release_sha256"]) != SHA256_HEX_LENGTH
            or not isinstance(value.get("validated_checkpoint_sha256"), str)
            or len(value["validated_checkpoint_sha256"]) != SHA256_HEX_LENGTH
            or not _valid_keys(value.get("obligation_keys"))):
        return None
    return value


def _no_admission_since(run_dir: Path, tip, validated_checkpoint_sha256: str) -> bool:
    from bilqis_mlx.runtime.bamf_bundle.atlas_admission import ATLAS_ADMISSION_SCHEMAS
    from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
        FACTORY_RELEASE_ADMISSION_SCHEMAS,
    )
    from bilqis_mlx.runtime.bamf_bundle.publication import ACCEPTANCE_DIR
    from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
        load_accepted_authority_checkpoint,
    )
    from bilqis_mlx.runtime.bamf_bundle.records import sha

    current = tip
    while current.digest != validated_checkpoint_sha256:
        path = Path(run_dir) / ACCEPTANCE_DIR / f"{current.manifest_sha256}.json"
        if path.is_symlink() or not path.is_file():
            return False
        try:
            raw = path.read_bytes()
            if sha(raw) != current.acceptance_file_sha256:
                return False
            record = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        if record.get("schema_version") in (
                ATLAS_ADMISSION_SCHEMAS | FACTORY_RELEASE_ADMISSION_SCHEMAS):
            return False
        if current.parent_checkpoint_sha256 is None:
            return False
        current = load_accepted_authority_checkpoint(current.parent_checkpoint_sha256)
    return True


def load_accepted_obligation_projection(run_dir: Path, pointer: dict):
    """Reuse a deeply derived credit only across ordinary accepted descendants."""
    value = _record(run_dir)
    if value is None or value["run_id"] != pointer.get("run_id"):
        return None
    from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
        accepted_authority_tip_extends_checkpoint,
        read_protected_accepted_authority_tip,
    )
    tip = read_protected_accepted_authority_tip(value["run_id"])
    if (tip is None
            or tip.manifest_sha256 != pointer.get("manifest_sha256")
            or tip.acceptance_sha256 != pointer.get("acceptance_sha256")
            or tip.factory_release_sha256 != value["factory_release_sha256"]
            or not accepted_authority_tip_extends_checkpoint(
                value["run_id"], value["validated_checkpoint_sha256"])
            or not _no_admission_since(
                run_dir, tip, value["validated_checkpoint_sha256"])):
        return None
    keys = tuple(tuple(item) for item in value["obligation_keys"])
    return tip.factory_release_sha256, tip.acceptance_sha256, keys


def persist_accepted_obligation_projection(
        run_dir: Path, pointer: dict, factory_release_sha256: str,
        obligation_keys: tuple[tuple[str, str], ...]) -> None:
    """Memoize one authenticated history result; never mint accepted authority."""
    from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
        read_protected_accepted_authority_tip,
    )
    run_id = pointer.get("run_id")
    tip = read_protected_accepted_authority_tip(run_id) if isinstance(run_id, str) else None
    if (tip is None
            or tip.manifest_sha256 != pointer.get("manifest_sha256")
            or tip.acceptance_sha256 != pointer.get("acceptance_sha256")
            or tip.factory_release_sha256 != factory_release_sha256):
        return
    path = _memo_path(run_dir)
    if (path.is_symlink() or path.parent.is_symlink()
            or (path.parent.exists() and not path.parent.is_dir())):
        return
    _durable_json(path, {
        "schema": _SCHEMA,
        "run_id": run_id,
        "factory_release_sha256": factory_release_sha256,
        "obligation_keys": [list(item) for item in obligation_keys],
        "validated_checkpoint_sha256": tip.digest,
    }, replace_existing=True)


__all__ = (
    "load_accepted_obligation_projection",
    "persist_accepted_obligation_projection",
)
