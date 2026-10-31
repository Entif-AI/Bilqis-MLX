from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lib.ithkuil.src.ingestion_semantic import (
    _csv_paths,
    _input_hashes,
    _validate_source_result,
    run_semantic,
)


REPO = REPO_ROOT
ITHKUIL = REPO / "lib" / "ithkuil"
CSV = ITHKUIL / "_data" / "csv"
PYTHON = REPO / ".venv" / "bin" / "python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha(path)
            for path in sorted(root.rglob("*.csv"))}


def copied_csv(parent: Path) -> Path:
    target = parent / "csv"
    shutil.copytree(CSV, target)
    return target


class SemanticIngestionTests(unittest.TestCase):
    def test_calls_both_canonical_owners_and_surfaces_distinct_bound_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = copied_csv(root)
            before = csv_hashes(data)
            result = run_semantic(
                REPO, str(PYTHON), data, data / "sources/extraction_frontier.json",
                root / "semantic-output",
            )

            self.assertEqual(result["status"], "SUCCEEDED", result)
            self.assertEqual([item["stage"] for item in result["commands"]],
                             ["core_build", "full_conformance"])
            self.assertTrue(all(item["exit_code"] == 0 for item in result["commands"]))
            self.assertEqual(result["validator"]["csv_preflight_passed"], True)
            self.assertEqual(result["input_identity"]["frontier_receipt_sha256"],
                             json.loads((data / "sources/extraction_frontier.json").read_text())[
                                 "receipt_sha256"])

            core = result["artifacts"]["core_generation_bundle"]
            full = result["artifacts"]["full_conformance_bundle"]
            self.assertEqual(core["status"], "partial")
            self.assertTrue(core["release_ineligible"])
            self.assertEqual(core["canonical"]["sha256"], core["digest"]["canonical_sha256"])
            self.assertEqual(core["digest"]["input_closure_sha256"],
                             result["input_identity"]["csv_closure_sha256"])
            self.assertNotEqual(core["canonical"]["sha256"], full["canonical"]["sha256"])
            self.assertEqual(full["status"], "complete")
            self.assertEqual(full["coverage_status"], "partial")
            self.assertEqual([gate["gate"] for gate in full["gates"]],
                             ["coverage", "no-omission", "determinism", "shacl"])
            self.assertTrue(all(gate["status"] == "passed" for gate in full["gates"]))
            self.assertEqual(result["graph_eligibility"]["eligible"], True)
            self.assertEqual(result["graph_eligibility"]["reason"], "ALL_GATES_PASSED")
            self.assertEqual(result["graph_eligibility"]["release_qualified"], False)
            self.assertEqual(before, csv_hashes(data))
            self.assertTrue(Path(core["manifest"]["path"]).is_file())
            self.assertTrue(Path(full["manifest"]["path"]).is_file())

    def test_real_conformance_owner_failure_is_named_and_blocks_graph_eligibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = copied_csv(root)
            before = csv_hashes(data)

            from lib.ithkuil.tests.ingestion_failure_injection import fail_no_omission

            result = run_semantic(
                REPO, str(PYTHON), data, data / "sources/extraction_frontier.json",
                root / "semantic-output", command_runner=fail_no_omission,
            )

            self.assertEqual(result["status"], "FAILED", result)
            self.assertEqual(result["failed_stage"], "full_conformance")
            self.assertEqual(result["failed_gates"], ["no-omission"])
            failed = next(gate for gate in result["artifacts"]["full_conformance_bundle"]["gates"]
                          if gate["gate"] == "no-omission")
            self.assertEqual(failed["status"], "failed")
            self.assertTrue(failed["evidence"])
            self.assertEqual(result["graph_eligibility"]["eligible"], False)
            self.assertEqual([item["stage"] for item in result["commands"]],
                             ["core_build", "full_conformance"])
            self.assertFalse(any("falkor" in " ".join(item["argv"]).lower()
                                 for item in result["commands"]))
            self.assertTrue(Path(result["artifacts"]["full_conformance_bundle"]["manifest"]["path"]).is_file())
            self.assertEqual(before, csv_hashes(data))

    def test_failed_stage_a_result_blocks_before_output_or_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = copied_csv(root)
            output = root / "semantic-output"
            result = run_semantic(
                REPO, str(PYTHON), data, data / "sources/extraction_frontier.json", output,
                source_result={"status": "FAILED", "validator": {"passed": False}},
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["failed_stage"], "inspect")
            self.assertEqual(result["commands"], [])
            self.assertFalse(output.exists())

    def test_valid_stage_a_result_binds_full_published_csv_set_and_frontier(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical_root = root / "canonical"
            data = canonical_root / "_data" / "csv"
            data.parent.mkdir(parents=True)
            shutil.copytree(CSV, data)
            frontier_path = data / "sources/extraction_frontier.json"
            frontier_sha = sha(frontier_path)
            published = {"_data/csv/" + path.name: sha(path)
                         for path in data.glob("*.csv")}
            published["_data/csv/sources/extraction_frontier.json"] = frontier_sha
            result = {
                "status": "SUCCEEDED", "source_manifest_sha256": sha(data / "sources/source_manifest.csv"),
                "validator": {"passed": True},
                "artifacts": {"canonical_root": str(canonical_root),
                              "published_artifact_hashes": published},
                "frontier": {"path": str(frontier_path), "sha256": frontier_sha},
            }
            selected_paths = _csv_paths(data)
            selected_hashes = _input_hashes(data, selected_paths)
            checked = _validate_source_result(
                result, "b" * 64, data.resolve(), frontier_path.resolve(), frontier_sha,
                selected_hashes,
            )
            self.assertTrue(checked["provided"])
            self.assertTrue(checked["stage_a_success"])

            top_csv = next(data.glob("*.csv"))
            published["_data/csv/" + top_csv.name] = "0" * 64
            with self.assertRaisesRegex(ValueError, "STAGE_A_CSV_IDENTITY_MISMATCH"):
                _validate_source_result(result, "b" * 64, data.resolve(), frontier_path.resolve(),
                                        frontier_sha, selected_hashes)
            published["_data/csv/" + top_csv.name] = sha(top_csv)
            result["source_manifest_sha256"] = "a" * 64
            with self.assertRaisesRegex(ValueError, "STAGE_A_SOURCE_MANIFEST_IDENTITY_MISSING"):
                _validate_source_result(result, "b" * 64, data.resolve(), frontier_path.resolve(),
                                        frontier_sha, selected_hashes)

    def test_stale_frontier_csv_binding_blocks_without_mutating_the_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = copied_csv(root)
            target = data / "morphemes_atomic.csv"
            target.write_bytes(target.read_bytes() + b"\n")
            before = csv_hashes(data)
            output = root / "semantic-output"
            result = run_semantic(
                REPO, str(PYTHON), data, data / "sources/extraction_frontier.json", output,
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["failed_stage"], "inspect")
            self.assertIn("FRONTIER_CSV_IDENTITY_MISMATCH", result["error_code"])
            self.assertEqual(result["commands"], [])
            self.assertFalse(output.exists())
            self.assertEqual(before, csv_hashes(data))


if __name__ == "__main__":
    unittest.main()
