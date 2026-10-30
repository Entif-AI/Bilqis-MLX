"""Reproduce the pinned A01 artifact from a verified full-domain source bundle.

This restores disposable test inputs. It does not extract new raw sources,
change semantic pins, admit a curriculum, or touch learner state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bilqis_mlx.semantics.atlas_projection import (
    FormalDomainBinding, compile_atlas_release, persist_atlas_release,
    validate_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
SEMANTICS = ROOT / "bilqis_mlx/semantics"


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebuild(source_bundle: Path, output_root: Path) -> dict:
    """Replay A01.2's recorded formal bindings and require its independent pin."""
    entries = json.loads((SEMANTICS / "atlas_source_pins_v1.json").read_bytes())["entries"]
    matches = [entry for entry in entries if entry["source_bundle_id"] == source_bundle.name]
    if len(matches) != 1:
        raise ValueError("source bundle must identify exactly one recorded A01 release")
    pin = matches[0]
    bindings = (
        FormalDomainBinding(
            "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json",
            _fingerprint(SEMANTICS / "legacy_abi_v1.json"),
            ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
            ("B.NOT", "B.AND")),
        FormalDomainBinding(
            "numeric", "bilqis_mlx/semantics/numeric_v1.json",
            _fingerprint(SEMANTICS / "numeric_v1.json"),
            ("bilqis.numeric/v1:school.op.COUNT", "bilqis.numeric/v1:school.op.SUCC"),
            ("C.COUNT", "C.SUCCESSOR")),
    )
    coverage = json.loads((source_bundle / "coverage.json").read_bytes())
    release = compile_atlas_release(
        source_bundle, coverage, SEMANTICS / "copular_registry_v1.json", bindings)
    validate_atlas_release(release)
    if release.digest != pin["release_sha256"]:
        raise ValueError("rebuilt Atlas release differs from its recorded A01 pin")
    receipt = persist_atlas_release(release, output_root)
    if receipt.bundle_id != pin["bundle_id"]:
        raise ValueError("rebuilt Atlas artifact differs from its recorded A01 pin")
    selection = AtlasArtifactSelection(
        str(receipt.path), pin["bundle_id"], pin["release_sha256"], pin["source_bundle_id"])
    snapshot = load_pinned_atlas_snapshot(selection)
    return {
        "artifact_path": str(receipt.path),
        "bundle_id": snapshot.bundle_id,
        "release_sha256": snapshot.release_sha256,
        "source_bundle_id": snapshot.source_bundle_id,
        "disposition": "REPRODUCED_PINNED_ARTIFACT_NOT_NEURAL_ADMISSION",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-bundle", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild(args.source_bundle.resolve(), args.output_root.resolve()),
                     sort_keys=True))


if __name__ == "__main__":
    main()
