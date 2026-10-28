"""Build canonical RDF, held accounting and digests from explicit tracked CSVs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .builder import build_core_graph
from .canonical import canonicalize
from .errors import ProfileError
from .ledger import build_ledger, ledger_json_bytes
from .preflight import CompilerClosure, preflight
from .publication import ArtifactBundle, json_bytes, make_bundle, publish_bundle
from .resolver import resolve_identities
from .source import SourceProjector


LIB_ROOT = Path(__file__).resolve().parents[2]
PROFILE_VERSION = "bilqis-skos-profile/1"
COMPILER_VERSION = "bilqis-skos-compiler/1"


def input_receipt(closure: CompilerClosure) -> dict:
    """Hash exact loaded values, with row/column ordering excluded from identity."""
    tables = {}
    for table in sorted(closure.tables, key=lambda item: item.name):
        rows = sorted(
            json.dumps(dict(row.values), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            for row in table.rows
        )
        digest = hashlib.sha256()
        for row in rows:
            digest.update(row + b"\n")
        tables[table.name] = {"rows": len(rows), "columns": sorted(table.columns), "sha256": digest.hexdigest()}
    body = {"schema": "bilqis.skos.input-closure/v1", "manifest_version": closure.manifest_version,
            "normalization": "exact-values-sorted-json-rows/v1", "tables": tables}
    return {**body, "sha256": hashlib.sha256(json_bytes(body)).hexdigest()}


def compiler_receipt() -> dict:
    package = Path(__file__).resolve().parent
    paths = sorted([*package.glob("*.py"), *package.glob("*.json"),
                    LIB_ROOT / "SKOS_PROFILE.md", LIB_ROOT / "SKOS_COMPILER.md",
                    LIB_ROOT / "requirements-semantic.txt"])
    hashes = {path.relative_to(LIB_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in paths}
    return {"version": COMPILER_VERSION, "files": hashes,
            "sha256": hashlib.sha256(json_bytes(hashes)).hexdigest()}


def compile_corpus(input_root: str | Path, *, profile_version: str = PROFILE_VERSION) -> ArtifactBundle:
    """Run all pure semantic stages before the publication boundary can write files."""
    if profile_version != PROFILE_VERSION:
        raise ProfileError("UNSUPPORTED_COMPILER_PROFILE", profile_version)
    closure = preflight(input_root).require_valid()
    profile_digest = hashlib.sha256((LIB_ROOT / "SKOS_PROFILE.md").read_bytes()).hexdigest()
    resolution = resolve_identities(closure)
    projector = SourceProjector(closure)
    built = build_core_graph(resolution.resources, projector)
    ledger = build_ledger(closure, resolution, built,
                          profile_version=profile_version, profile_digest=profile_digest)
    if ledger.blocking:
        raise ProfileError("COMPILER_ACCOUNTING_BLOCKED",
                           *(diagnostic.code for diagnostic in ledger.diagnostics if diagnostic.blocking))
    canonical = canonicalize(built.graph)
    inputs = input_receipt(closure)
    compiler = compiler_receipt()
    digest = {**canonical.metadata(), "profile_version": profile_version,
              "profile_sha256": profile_digest, "input_closure_sha256": inputs["sha256"],
              "compiler": compiler}
    status = "partial" if ledger.release_ineligible else "complete"
    files = {"canonical.nt": canonical.payload, "held.json": ledger_json_bytes(ledger),
             "digest.json": json_bytes(digest), "input.json": json_bytes(inputs)}
    return make_bundle(files, {
        "status": status, "release_ineligible": ledger.release_ineligible,
        "profile_version": profile_version, "profile_sha256": profile_digest,
        "compiler_version": COMPILER_VERSION, "compiler_sha256": compiler["sha256"],
        "input_closure_sha256": inputs["sha256"], "canonical_sha256": canonical.sha256,
        "triple_count": canonical.triple_count, "emitted_resources": len(built.emitted),
        "resolved_resources": len(resolution.resources),
    })


def build(input_root: str | Path, output_root: str | Path, *, profile_version: str = PROFILE_VERSION) -> dict:
    raw_target = Path(output_root)
    if raw_target.is_symlink():
        raise ProfileError("OUTPUT_ROOT_SYMLINK_FORBIDDEN")
    source, target = Path(input_root).resolve(), raw_target.resolve()
    if target == source or target.is_relative_to(source):
        raise ProfileError("OUTPUT_INSIDE_SOURCE_ROOT")
    if target == LIB_ROOT or target.is_relative_to(LIB_ROOT / "src"):
        raise ProfileError("OUTPUT_INSIDE_COMPILER_SOURCE")
    bundle = compile_corpus(source, profile_version=profile_version)
    receipt = publish_bundle(bundle, target)
    metadata = receipt["metadata"]
    summary = {"status": metadata["status"], "bundle_id": receipt["bundle_id"],
            "output_root": str(target), "generation": receipt["path"],
            "canonical_sha256": metadata["canonical_sha256"],
            "triple_count": metadata["triple_count"],
            "emitted_resources": metadata["emitted_resources"],
            "resolved_resources": metadata["resolved_resources"],
            "release_ineligible": metadata["release_ineligible"]}
    if receipt.get("durability_warning"):
        summary["durability_warning"] = receipt["durability_warning"]
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=LIB_ROOT / "_data/csv",
                        help="Tracked CSV root; default is the package's _data/csv directory.")
    parser.add_argument("--output-root", type=Path, required=True,
                        help="Artifact directory containing immutable generations and CURRENT.json.")
    parser.add_argument("--profile", default=PROFILE_VERSION, help="Explicit supported semantic profile version.")
    args = parser.parse_args(argv)
    try:
        result = build(args.input_root, args.output_root, profile_version=args.profile)
    except ProfileError as error:
        status = ("reconcile_required" if error.code == "COMPILER_PUBLICATION_COMMITTED_READBACK_REQUIRED"
                  else "blocked")
        print(json.dumps({"status": status, **error.as_dict()}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    except OSError as error:
        print(json.dumps({"status": "blocked", "code": "COMPILER_IO_ERROR", "details": [type(error).__name__]}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
