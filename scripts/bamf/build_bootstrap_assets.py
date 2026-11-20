#!/usr/bin/env python3
"""Build the small repository-owned source seed used by fresh BAMF creation."""
from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bilqis_mlx.bootstrap_assets import SOURCE_RUN
from bilqis_mlx.compatibility.executable_projection import (
    LIVE_V2_VERIFICATION_SEED,
    project_legacy_course,
)
from bilqis_mlx.compatibility.live_releases import (
    boolean_composite_successor,
    boolean_identification_successor,
    boolean_successor,
    initial_course,
    numeric_successor,
)
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.live_grade_c import REGISTRY_COUNTING_TARGET, registry_graph
from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.runtime.mlx_checkpoint import digest_file
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.vocabulary_growth import digest


LEGACY = ROOT / "vendor" / "legacy-v16"
GRADE_A_MANIFEST = ROOT / "docs" / "provenance" / "GRADE_A_CANDIDATE_MANIFEST_V2.json"
ORIGIN = Checkpoint(
    "f8192bd851f7088849388025b6190ea567dbe1c149fa19ef78665a2f6af11812",
    "bundles/best-18299-f9ebf690c79b",
    134808,
    True,
)


def _canonical(record: object) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _school_release():
    manifest = json.loads(GRADE_A_MANIFEST.read_text(encoding="utf-8"))
    grade_a = initial_course(accepted_grade_a(manifest))
    course = boolean_successor(grade_a, LEGACY)
    course = boolean_composite_successor(course, LEGACY)
    course = boolean_identification_successor(course, LEGACY)
    course, _ = numeric_successor(course, maximum=REGISTRY_COUNTING_TARGET)
    answers = live_answer_registry()
    curriculum, bindings, profile, _ = project_legacy_course(
        course,
        grade_a,
        LEGACY,
        answer_kinds=answers.kinds,
    )
    graph = registry_graph()
    release = compile_executable_factory_release(
        curriculum,
        bindings,
        profile,
        live_source_registry(),
        answers,
        source_root=LEGACY,
        graph=graph,
        verification_seed=LIVE_V2_VERIFICATION_SEED,
    )
    return course, graph, release


def build(destination: Path) -> None:
    destination = Path(destination)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    course, graph, release = _school_release()
    _, release_file, admission = _executable_factory_admission(
        destination,
        release,
        ORIGIN,
        _fingerprint(graph),
        graph,
    )

    bundle = destination / ORIGIN.filename
    bundle.mkdir(parents=True)
    catalog = bundle / "semantic-catalog.json"
    catalog.write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    binding = {
        "filename": catalog.name,
        "digest": digest(graph),
        "token_count": len(graph["tokens"]),
        "file_sha256": digest_file(catalog),
    }
    (bundle / "manifest.json").write_text(
        _canonical({"semantic_catalog": binding}),
        encoding="utf-8",
    )

    state = {
        "generation": 0,
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_admission_v2": asdict(admission),
        "semantic_graph_sha256": _fingerprint(graph),
        "model_bundle": ORIGIN.filename,
        "school": {
            "current_student": asdict(ORIGIN),
            "active_grades": [grade.id for grade in course.grades],
            "grade_index": 0,
            "visits": 0,
            "stage": "FOUNDATION",
        },
        "result": "BOOTSTRAP_SOURCE_SEED",
    }
    payload = _canonical(state)
    (destination / "state.json").write_text(payload, encoding="utf-8")
    states = destination / "states"
    states.mkdir()
    (states / "0000000.json").write_text(payload, encoding="utf-8")


def _snapshot(root: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        (str(path.relative_to(root)), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def check() -> bool:
    with tempfile.TemporaryDirectory(prefix="bilqis-bootstrap-seed-") as temp:
        candidate = Path(temp) / "source-run"
        build(candidate)
        return _snapshot(candidate) == _snapshot(SOURCE_RUN)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=SOURCE_RUN)
    args = parser.parse_args()
    if args.check:
        if not check():
            print("BAMF bootstrap source seed is stale", file=sys.stderr)
            return 1
        print("BAMF bootstrap source seed is current")
        return 0
    build(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
