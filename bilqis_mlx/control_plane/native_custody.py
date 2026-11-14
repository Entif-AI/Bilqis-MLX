"""Read-only authentication of the accepted BAMF generation chain."""
from __future__ import annotations

import json
from pathlib import Path

from .native_contracts import (
    AuthenticatedGeneration, canonical, invalid, is_digest, native_outbox_event_id,
    sha,
)


_BUNDLE_V3 = "bilqis.mlx.bamf-generation-bundle/v3"
_POINTER = "bamf-state.json"


def _read_json(path: Path, *, reason: str):
    if path.is_symlink() or not path.is_file():
        invalid(reason)
    try:
        return json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        invalid(reason)


def _read_bound_json(root: Path, binding: dict, *, reason: str):
    if not isinstance(binding, dict):
        invalid(reason)
    filename = binding.get("filename")
    digest = binding.get("sha256")
    if (not isinstance(filename, str) or Path(filename).name != filename
            or not is_digest(digest)
            or (binding.get("object_sha256") is not None
                and binding.get("object_sha256") != digest)):
        invalid(reason)
    path = root / filename
    if path.is_symlink() or not path.is_file():
        invalid(reason)
    raw = path.read_bytes()
    if sha(raw) != digest:
        invalid(reason)
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid(reason)


def _accepted_generation(
    run_dir: Path, manifest_sha256: str, acceptance_sha256: str,
) -> AuthenticatedGeneration:
    if not is_digest(manifest_sha256) or not is_digest(acceptance_sha256):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_ANCHOR_INVALID")
    root = run_dir / "bamf-bundles" / manifest_sha256
    manifest_path = root / "manifest.json"
    if (root.is_symlink() or not root.is_dir() or manifest_path.is_symlink()
            or not manifest_path.is_file()):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_BUNDLE_INVALID")
    raw_manifest = manifest_path.read_bytes()
    if sha(raw_manifest) != manifest_sha256:
        invalid("CONTROL_PLANE_NATIVE_HISTORY_MANIFEST_DRIFT")
    try:
        manifest = json.loads(raw_manifest)
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_MANIFEST_INVALID")
    if (not isinstance(manifest, dict) or manifest.get("run_id") is None
            or type(manifest.get("generation")) is not int
            or not isinstance(manifest.get("sidecars"), dict)
            or not isinstance(manifest.get("optimizer"), dict)
            or not isinstance(manifest.get("provenance"), dict)
            or not isinstance(manifest.get("topology"), dict)):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_MANIFEST_INVALID")
    acceptance = _read_json(
        run_dir / "bamf-acceptance" / f"{manifest_sha256}.json",
        reason="CONTROL_PLANE_NATIVE_HISTORY_ACCEPTANCE_INVALID")
    if not isinstance(acceptance, dict):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_ACCEPTANCE_INVALID")
    public = {key: value for key, value in acceptance.items() if key != "binding_sha256"}
    if (acceptance.get("binding_sha256") != acceptance_sha256
            or sha(canonical(public)) != acceptance_sha256
            or acceptance.get("run_id") != manifest["run_id"]
            or acceptance.get("generation") != manifest["generation"]
            or ("optimizer_step" in acceptance
                and acceptance["optimizer_step"] != manifest["optimizer"].get("step"))
            or not is_digest(acceptance.get("candidate_identity_sha256"))):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_ACCEPTANCE_DRIFT")
    outbox = _read_bound_json(
        root, manifest["sidecars"].get("outbox"),
        reason="CONTROL_PLANE_NATIVE_HISTORY_OUTBOX_INVALID")
    if not isinstance(outbox, list) or not outbox:
        invalid("CONTROL_PLANE_NATIVE_HISTORY_OUTBOX_INVALID")
    seen = set()
    for index, event in enumerate(outbox):
        if (not isinstance(event, dict) or not is_digest(event.get("event_id"))
                or event["event_id"] in seen):
            invalid("CONTROL_PLANE_NATIVE_HISTORY_OUTBOX_INVALID")
        payload = {key: value for key, value in event.items() if key != "event_id"}
        if event["event_id"] != native_outbox_event_id(
                manifest["run_id"], manifest["generation"], index, payload):
            invalid("CONTROL_PLANE_NATIVE_HISTORY_OUTBOX_INVALID")
        seen.add(event["event_id"])
    identity = _read_bound_json(
        root, manifest["sidecars"].get("run_identity"),
        reason="CONTROL_PLANE_NATIVE_HISTORY_RUN_IDENTITY_INVALID")
    if (not isinstance(identity, dict) or identity.get("run_id") != manifest["run_id"]
            or not is_digest(identity.get("run_identity_sha256"))):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_RUN_IDENTITY_INVALID")
    identity_public = {
        key: value for key, value in identity.items() if key != "run_identity_sha256"}
    if sha(canonical(identity_public)) != identity["run_identity_sha256"]:
        invalid("CONTROL_PLANE_NATIVE_HISTORY_RUN_IDENTITY_INVALID")
    teacher_state = _read_bound_json(
        root, manifest["sidecars"].get("teacher_state"),
        reason="CONTROL_PLANE_NATIVE_HISTORY_TEACHER_STATE_INVALID")
    if not isinstance(teacher_state, dict):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_TEACHER_STATE_INVALID")
    return AuthenticatedGeneration(
        manifest_sha256, acceptance_sha256, manifest, acceptance, identity,
        teacher_state, tuple(outbox))


def authenticated_history(run_dir: Path) -> tuple[AuthenticatedGeneration, ...]:
    """Return oldest->newest history anchored by the accepted BAMF pointer."""
    run_dir = Path(run_dir).expanduser().resolve()
    from bilqis_mlx.runtime.bamf_bundle import inspect_accepted_generation

    before = inspect_accepted_generation(run_dir / _POINTER)
    manifest_sha = before.generation_manifest_sha256
    acceptance_sha = before.acceptance_sha256
    reverse = []
    expected_generation = before.generation
    while True:
        generation = _accepted_generation(run_dir, manifest_sha, acceptance_sha)
        manifest = generation.manifest
        if (manifest["run_id"] != before.run_id
                or manifest["generation"] != expected_generation
                or generation.run_identity["run_identity_sha256"]
                != before.run_identity_sha256):
            invalid("CONTROL_PLANE_NATIVE_HISTORY_LINEAGE_DRIFT")
        reverse.append(generation)
        parent_sha = manifest.get("parent_manifest_sha256")
        if parent_sha is None:
            if manifest["generation"] != 0:
                invalid("CONTROL_PLANE_NATIVE_HISTORY_LINEAGE_DRIFT")
            break
        if manifest.get("schema") != _BUNDLE_V3:
            invalid("CONTROL_PLANE_NATIVE_HISTORY_PARENT_UNAUTHENTICATED")
        parent_acceptance = manifest.get("parent_acceptance_sha256")
        if not is_digest(parent_sha) or not is_digest(parent_acceptance):
            invalid("CONTROL_PLANE_NATIVE_HISTORY_PARENT_UNAUTHENTICATED")
        expected_generation -= 1
        if expected_generation < 0:
            invalid("CONTROL_PLANE_NATIVE_HISTORY_LINEAGE_DRIFT")
        manifest_sha, acceptance_sha = parent_sha, parent_acceptance
    after = inspect_accepted_generation(run_dir / _POINTER)
    if after != before:
        invalid("CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED")
    return tuple(reversed(reverse))


__all__ = ("AuthenticatedGeneration", "authenticated_history")
