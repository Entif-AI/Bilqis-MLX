"""Atlas projection bundle ownership; canonical algorithms preserved."""
from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
import json
from .common import GATE_VERSIONS, HEX64, REQUIRED_BUNDLE_FILES, REQUIRED_GATES, _canonical_bytes, _digest, _fail


def _verify_bundle(root: Path) -> tuple[str, dict[str, bytes]]:
    if root.is_symlink() or not root.is_dir():
        _fail("ATLAS_SOURCE_BUNDLE_INVALID")
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        _fail("ATLAS_SOURCE_MANIFEST_INVALID")
    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = json.loads(manifest_payload)
    except (OSError, ValueError, UnicodeError) as error:
        _fail("ATLAS_SOURCE_MANIFEST_INVALID:" + type(error).__name__)
    if (not isinstance(manifest, dict) or set(manifest) != REQUIRED_BUNDLE_FILES
            or any(not isinstance(name, str) or not isinstance(sha, str)
                   or not HEX64.fullmatch(sha) for name, sha in manifest.items())):
        _fail("ATLAS_SOURCE_MANIFEST_INVALID")
    if manifest_payload != _canonical_bytes(manifest):
        _fail("ATLAS_SOURCE_MANIFEST_NONCANONICAL")
    expected_members = REQUIRED_BUNDLE_FILES | {"manifest.json"}
    try:
        members = tuple(root.iterdir())
    except OSError as error:
        _fail("ATLAS_SOURCE_BUNDLE_INVALID:" + type(error).__name__)
    if ({path.name for path in members} != expected_members
            or any(path.is_symlink() or not path.is_file() for path in members)):
        _fail("ATLAS_SOURCE_BUNDLE_MEMBER_SET_INVALID")
    bundle_id = _digest(manifest_payload)
    if HEX64.fullmatch(root.name) and root.name != bundle_id:
        _fail("ATLAS_SOURCE_BUNDLE_ID_MISMATCH")
    payloads: dict[str, bytes] = {}
    for name, expected in sorted(manifest.items()):
        path = root / name
        if path.is_symlink() or not path.is_file():
            _fail("ATLAS_SOURCE_ARTIFACT_MISSING:" + name)
        payload = path.read_bytes()
        if _digest(payload) != expected:
            _fail("ATLAS_SOURCE_ARTIFACT_DIGEST_MISMATCH:" + name)
        payloads[name] = payload
    return bundle_id, payloads

def _validated_gates(conformance: dict, payloads: Mapping[str, bytes]) -> dict[str, dict]:
    gates = conformance.get("gates")
    if not isinstance(gates, list) or len(gates) != len(REQUIRED_GATES):
        _fail("ATLAS_CONFORMANCE_GATES_INVALID")
    result: dict[str, dict] = {}
    for gate in gates:
        if (not isinstance(gate, dict)
                or set(gate) != {"gate", "version", "status", "evidence"}
                or gate.get("gate") not in REQUIRED_GATES
                or gate.get("version") != GATE_VERSIONS[gate["gate"]]
                or gate.get("status") != "passed"
                or not isinstance(gate.get("evidence"), dict)
                or gate["gate"] in result):
            _fail("ATLAS_CONFORMANCE_GATES_INVALID")
        result[gate["gate"]] = gate
    if set(result) != REQUIRED_GATES:
        _fail("ATLAS_CONFORMANCE_GATES_INVALID")
    for gate_name, aggregate in result.items():
        file_name = "gate-" + gate_name + ".json"
        try:
            constituent = json.loads(payloads[file_name])
        except (ValueError, TypeError, UnicodeError) as error:
            _fail("ATLAS_CONFORMANCE_GATE_FILE_INVALID:" + gate_name + ":" + type(error).__name__)
        if (not isinstance(constituent, dict)
                or payloads[file_name] != _canonical_bytes(constituent)
                or constituent != aggregate):
            _fail("ATLAS_CONFORMANCE_GATE_MISMATCH:" + gate_name)
    return result
