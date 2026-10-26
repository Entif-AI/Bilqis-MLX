"""Canonical semantic-build determinism checker for issue #70."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import sys

from rdflib import Graph

from .build import compile_corpus
from .canonical import canonical_diff, canonicalize
from .errors import ProfileError
from .publication import ArtifactBundle
from .rdf_read import read_canonical_graph


@dataclass(frozen=True, order=True)
class DeterminismCase:
    scenario: str
    equal: bool
    before_sha256: str
    after_sha256: str
    before_triples: int
    after_triples: int
    first_removed: str | None
    first_added: str | None

    def as_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "equal": self.equal,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "before_triples": self.before_triples,
            "after_triples": self.after_triples,
            "first_removed": self.first_removed,
            "first_added": self.first_added,
        }


@dataclass(frozen=True)
class DeterminismReport:
    cases: tuple[DeterminismCase, ...]

    @property
    def deterministic(self) -> bool:
        return all(case.equal for case in self.cases)

    def as_dict(self) -> dict:
        return {
            "schema": "bilqis.skos.determinism-report/v1",
            "deterministic": self.deterministic,
            "cases": [case.as_dict() for case in self.cases],
        }


def compare_graphs(reference: Graph, candidate: Graph, *, scenario: str) -> DeterminismCase:
    if not isinstance(scenario, str) or not scenario:
        raise ProfileError("DETERMINISM_SCENARIO_REQUIRED")
    before = canonicalize(reference)
    after = canonicalize(candidate)
    diff = canonical_diff(reference, candidate, limit=1)
    removed = diff["removed"][0] if diff["removed"] else None
    added = diff["added"][0] if diff["added"] else None
    return DeterminismCase(
        scenario=scenario,
        equal=before.payload == after.payload,
        before_sha256=before.sha256,
        after_sha256=after.sha256,
        before_triples=before.triple_count,
        after_triples=after.triple_count,
        first_removed=removed,
        first_added=added,
    )


def compare_bundles(
    reference: ArtifactBundle,
    candidate: ArtifactBundle,
    *,
    scenario: str,
) -> DeterminismCase:
    if not isinstance(reference, ArtifactBundle) or not isinstance(candidate, ArtifactBundle):
        raise ProfileError("DETERMINISM_ARTIFACT_BUNDLE_REQUIRED")
    before_files, after_files = dict(reference.files), dict(candidate.files)
    if "canonical.nt" not in before_files or "canonical.nt" not in after_files:
        raise ProfileError("DETERMINISM_CANONICAL_ARTIFACT_REQUIRED")
    case = compare_graphs(
        read_canonical_graph(before_files["canonical.nt"]),
        read_canonical_graph(after_files["canonical.nt"]),
        scenario=scenario,
    )
    before_meta, after_meta = reference.metadata(), candidate.metadata()
    if before_meta.get("canonical_sha256") != case.before_sha256:
        raise ProfileError(
            "DETERMINISM_REFERENCE_RECEIPT_MISMATCH",
            str(before_meta.get("canonical_sha256")),
            case.before_sha256,
        )
    if after_meta.get("canonical_sha256") != case.after_sha256:
        raise ProfileError(
            "DETERMINISM_CANDIDATE_RECEIPT_MISMATCH",
            str(after_meta.get("canonical_sha256")),
            case.after_sha256,
        )
    return case


def require_equivalent(case: DeterminismCase) -> DeterminismCase:
    if case.equal:
        return case
    details = [
        f"scenario={case.scenario}",
        f"before_sha256={case.before_sha256}",
        f"after_sha256={case.after_sha256}",
    ]
    if case.first_removed is not None:
        details.append(f"first_removed={case.first_removed}")
    if case.first_added is not None:
        details.append(f"first_added={case.first_added}")
    raise ProfileError("CANONICAL_DETERMINISM_MISMATCH", *details)


def repeat_build_check(input_root: str | Path) -> DeterminismReport:
    first = compile_corpus(input_root)
    second = compile_corpus(input_root)
    return DeterminismReport((compare_bundles(first, second, scenario="repeat-build"),))


def determinism_json_bytes(report: DeterminismReport) -> bytes:
    return (
        json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = repeat_build_check(args.input_root)
        for case in report.cases:
            require_equivalent(case)
    except (ProfileError, OSError) as error:
        code = error.code if isinstance(error, ProfileError) else "DETERMINISM_IO_ERROR"
        details = list(map(str, error.details)) if isinstance(error, ProfileError) else [type(error).__name__]
        print(
            json.dumps({"status": "failed", "gate": "determinism", "code": code, "details": details}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"status": "passed", **report.as_dict()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
