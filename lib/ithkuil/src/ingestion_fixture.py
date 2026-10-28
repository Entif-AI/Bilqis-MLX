"""Bounded real-source workflow proof; never a production frontier rebuild."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path, PurePosixPath
import shutil
import sys

from lxml import html

from .build_morphology import Builder, extract_ch3_ca
from .build_structure import table_matrix
from .ingestion import _bytes, _sha, _write_atomic
from .ingestion_semantic import run_semantic
from .skos.preflight import preflight

SCHEMA = "bilqis.ithkuil.fixture-frontier/v1"
FRONTIER_NAME = "sources/fixture_frontier.json"
CLAIMS = {"production_admission": False, "full_new_ithkuil_coverage": False,
          "curriculum_admission": False}


def _file(root: Path, name: str, expected: str) -> Path:
    relative = PurePosixPath(name)
    path = root.joinpath(*relative.parts)
    if (relative.is_absolute() or ".." in relative.parts or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve()) or not path.is_file()):
        raise ValueError("FIXTURE_INPUT_UNSAFE:" + name)
    if _sha(path.read_bytes()) != expected:
        raise ValueError("FIXTURE_INPUT_PIN_MISMATCH:" + name)
    return path


def _rows(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


class ExcerptBuilder(Builder):
    """Bind canonical table ordinals to pinned excerpts; reuse every parser rule."""

    def __init__(self, data: Path, excerpts: dict):
        super().__init__(data_root=data, raw_root=data.parent / "unused-raw")
        self.excerpts = excerpts

    def table(self, source_id: str, table_index: int):
        return self.excerpts[(source_id, table_index)]


def extract_fixture(descriptor_path: Path, output: Path) -> dict:
    """Extract source semantics and bind the explicitly pinned support closure."""
    descriptor_path = Path(descriptor_path).resolve()
    root = descriptor_path.parent
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if (descriptor.get("schema") != "bilqis.ithkuil.ingestion-fixture/v1"
            or descriptor.get("scope") != "fixture_only" or descriptor.get("claims") != CLAIMS):
        raise ValueError("FIXTURE_PROFILE_INVALID")
    excerpt = descriptor["excerpt"]
    try:
        source = _file(root, excerpt["path"], excerpt["sha256"])
        configuration = descriptor["configuration_excerpt"]
        config_source = _file(root, configuration["path"], configuration["sha256"])
    except ValueError as error:
        raise ValueError("FIXTURE_EXCERPT_INVALID:" + str(error)) from error
    table = html.fromstring(source.read_bytes(), parser=html.HTMLParser(encoding="utf-8")).xpath("//table")[0]
    config_table = html.fromstring(config_source.read_bytes(), parser=html.HTMLParser(encoding="utf-8"))
    matrix = table_matrix(table)
    if _sha(_bytes(matrix)) != excerpt["matrix_sha256"]:
        raise ValueError("FIXTURE_EXCERPT_MATRIX_MISMATCH")
    # Validate the complete seed before creating any output. These are existing
    # admitted support rows, not rows claimed to be extracted by this workflow.
    seed = {name: _file(root / "csv", name, digest)
            for name, digest in descriptor["seed_csv"].items()}
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(root):
        raise ValueError("FIXTURE_OUTPUT_MUST_BE_NEW_AND_SEPARATE")
    data = output / "_data/csv"
    data.mkdir(parents=True)
    for name, path in seed.items():
        target = data / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    builder = ExcerptBuilder(data, {("NI-WEB-CH03", 3): config_table,
                                    ("NI-WEB-CH03", 35): table})
    extract_ch3_ca(builder)
    generated = {
        "morphemes_atomic": ("atomic_id", builder.atomic),
        "morpheme_compositions": ("composition_id", builder.compositions),
        "composition_components": ("component_id", builder.components),
        "source_assertions": ("assertion_id", builder.assertions),
        "grammatical_categories": ("category_id", builder.categories),
        "allomorph_rules": ("allomorph_rule_id", builder.allomorph_rules),
    }
    for name, (key, extracted) in generated.items():
        path = data / (name + ".csv")
        fields, rows = _rows(path)
        merged = {row[key]: row for row in rows}
        # A canonical extractor result owns its own IDs. Any conflicting seed
        # must fail rather than silently overwrite a prior semantic statement.
        for identity, row in extracted.items():
            normalized = {field: str(row.get(field, "")) for field in fields}
            if identity in merged and merged[identity] != normalized:
                raise ValueError("FIXTURE_EXTRACTED_SEED_CONFLICT:" + identity)
            merged[identity] = normalized
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(merged[key] for key in sorted(merged))
    checked = preflight(data)
    if not checked.ok:
        raise ValueError("FIXTURE_RELATIONAL_VALIDATION_FAILED:" + ",".join(f.code for f in checked.findings))
    hashes = {path.relative_to(data).as_posix(): _sha(path.read_bytes())
              for path in sorted(data.rglob("*.csv"))}
    source_identity = {"descriptor_sha256": _sha(descriptor_path.read_bytes()),
                       "excerpt_sha256": excerpt["sha256"],
                       "configuration_excerpt_sha256": configuration["sha256"]}
    frontier = {"schema": SCHEMA, "scope": "fixture_only", "claims": CLAIMS,
                "fixture_id": descriptor["fixture_id"], "source_identity": source_identity,
                "inputs": hashes, "parser": "lib.ithkuil.src.build_morphology.extract_ch3_ca",
                "parser_sha256": _sha(Path(sys.modules[Builder.__module__].__file__).read_bytes()),
                "extracted_counts": {name: len(rows) for name, (_, rows) in generated.items()},
                "bound_seed": descriptor["seed_provenance"],
                "debt": {"seed_lexicon_debt": 1}}
    frontier["receipt_sha256"] = _sha(_bytes(frontier))
    frontier_path = data / FRONTIER_NAME
    _write_atomic(frontier_path, _bytes(frontier))
    frontier_sha = _sha(frontier_path.read_bytes())
    return {"schema": "bilqis.ithkuil.source-stage-result/v1", "status": "SUCCEEDED",
            "fixture_only": True, "source_manifest_sha256": hashes["sources/source_manifest.csv"],
            "source_input_identity": source_identity,
            "source_observation": {"table_id": "FIXTURE-91-CH03-T035:T001",
                                   "parent_table_id": descriptor["parent"]["table_id"],
                                   "table_row_count": len(matrix),
                                   "table_column_count": max(map(len, matrix)),
                                   "cell_count": sum(bool(c) for row in matrix for c in row),
                                   "matrix_sha256": _sha(_bytes(matrix))},
            "validator": {"passed": True, "owner": "lib.ithkuil.src.skos.preflight"},
            "frontier": {"path": str(frontier_path), "sha256": frontier_sha},
            "artifacts": {"canonical_root": str(output),
                          "published_artifact_hashes": {"_data/csv/" + name: digest for name, digest in hashes.items() if "/" not in name}
                          | {"_data/csv/" + FRONTIER_NAME: frontier_sha}}}


def run_fixture(repo: Path, python: str, descriptor: Path, output: Path) -> dict:
    result = {"schema": "bilqis.ithkuil.fixture-workflow/v1", "fixture_only": True,
              "status": "BLOCKED", "source_result": None, "semantic_result": None,
              "graph_result": None, "failed_stage": None, "error_code": None}
    try:
        if Path(repo).resolve() != Path(__file__).resolve().parents[3]:
            raise ValueError("REPOSITORY_MODULE_MISMATCH")
        target = Path(output).resolve()
        if target.exists() or target.is_relative_to(Path(repo).resolve()):
            raise ValueError("FIXTURE_OUTPUT_MUST_BE_NEW_AND_OUTSIDE_REPOSITORY")
        source = extract_fixture(descriptor, target / "source")
    except (OSError, ValueError, KeyError, IndexError) as error:
        return result | {"failed_stage": "source_fixture", "error_code": str(error)}
    result["source_result"] = source
    semantic = run_semantic(repo, python, Path(source["artifacts"]["canonical_root"]) / "_data/csv",
                            source["frontier"]["path"], Path(output) / "semantic", source_result=source)
    result["semantic_result"] = semantic
    if semantic["status"] != "SUCCEEDED":
        result.update(status="FAILED", failed_stage="semantic", error_code=semantic["error_code"])
    else:
        result.update(status="SUCCEEDED", graph_result={"status": "DISABLED"})
    _write_atomic(Path(output) / "fixture-result.json", _bytes(result))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_fixture(args.repo, args.python, args.descriptor, args.output_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
