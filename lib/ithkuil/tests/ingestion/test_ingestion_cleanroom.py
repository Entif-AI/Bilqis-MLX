from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import csv
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from lib.ithkuil.src.ingestion_fixture import run_fixture


REPO = REPO_ROOT
FIXTURE = FIXTURES / "ingestion"
PYTHON = REPO / ".venv" / "bin" / "python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha(path)
            for path in sorted(root.rglob("*")) if path.is_file() and not path.is_symlink()}


def copy_fixture(target: Path) -> Path:
    shutil.copytree(FIXTURE, target)
    return target


def semantic_receipt(result: dict) -> dict:
    semantic = result["semantic_result"]
    core = semantic["artifacts"]["core_generation_bundle"]
    full = semantic["artifacts"]["full_conformance_bundle"]
    return {
        "source_manifest_sha256": result["source_result"]["source_manifest_sha256"],
        "published_artifact_hashes": result["source_result"]["artifacts"][
            "published_artifact_hashes"],
        "frontier_receipt_sha256": semantic["input_identity"]["frontier_receipt_sha256"],
        "csv_closure_sha256": semantic["input_identity"]["csv_closure_sha256"],
        "core_canonical_sha256": core["canonical"]["sha256"],
        "core_held_sha256": core["held"]["sha256"],
        "full_bundle_id": full["bundle_id"],
        "full_canonical_sha256": full["canonical"]["sha256"],
        "coverage_sha256": full["coverage"]["sha256"],
        "conformance_sha256": full["conformance"]["sha256"],
        "gates": full["gates"],
    }


class CleanRoomIngestionTests(unittest.TestCase):
    def test_independent_runtime_copies_need_no_production_corpus(self):
        from lib.ithkuil.tests.ingestion_cleanroom import prove
        with tempfile.TemporaryDirectory() as temporary:
            receipt = prove(REPO, FIXTURE, Path(temporary) / "proof", str(PYTHON))
            self.assertEqual(receipt["differences"], [])
            self.assertEqual(receipt["independent_runtime_workspaces"], 2)

    def test_two_fresh_runs_reproduce_source_semantic_and_frontier_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = copy_fixture(root / "fixture")
            before = tree_hashes(fixture)
            first = run_fixture(REPO, str(PYTHON), fixture / "descriptor.json", root / "run-one")
            second = run_fixture(REPO, str(PYTHON), fixture / "descriptor.json", root / "run-two")

            for result in (first, second):
                self.assertEqual(result["status"], "SUCCEEDED", result)
                self.assertTrue(result["fixture_only"])
                self.assertEqual(result["source_result"]["status"], "SUCCEEDED")
                self.assertTrue(result["source_result"]["fixture_only"])
                self.assertTrue(result["source_result"]["validator"]["passed"])
                observation = result["source_result"]["source_observation"]
                self.assertEqual(observation["table_id"], "FIXTURE-91-CH03-T035:T001")
                self.assertEqual(observation["table_row_count"], 12)
                self.assertEqual(observation["table_column_count"], 14)
                self.assertEqual(observation["cell_count"], 90)
                self.assertEqual(observation["matrix_sha256"],
                                 "ddaecea945c2598d4848eee34faeb67cd8ffa472500e3652ede6edecb9f598e5")
                self.assertEqual(result["semantic_result"]["status"], "SUCCEEDED")
                self.assertTrue(result["semantic_result"]["input_identity"]["fixture_only"])
                self.assertEqual(result["semantic_result"]["validator"]["csv_preflight_passed"], True)
                self.assertEqual(result["graph_result"]["status"], "DISABLED")
                frontier = json.loads(Path(result["source_result"]["frontier"]["path"]).read_text())
                self.assertEqual(frontier["schema"], "bilqis.ithkuil.fixture-frontier/v1")
                self.assertEqual(frontier["scope"], "fixture_only")
                self.assertFalse(frontier["claims"]["full_new_ithkuil_coverage"])
                self.assertFalse(frontier["claims"]["production_admission"])
                self.assertEqual(frontier["extracted_counts"]["morphemes_atomic"], 52)
                data = Path(result["source_result"]["artifacts"]["canonical_root"]) / "_data/csv"
                with (data / "morphemes_atomic.csv").open(encoding="utf-8", newline="") as stream:
                    forms = [row["surface_form_raw"] for row in csv.DictReader(stream)
                             if row["category_code"] == "CONFIGURATION" and row["value_code"] == "MFF"]
                self.assertEqual(forms, ["ẓ"])
                self.assertEqual(frontier["parser"], "lib.ithkuil.src.build_morphology.extract_ch3_ca")
                full = result["semantic_result"]["artifacts"]["full_conformance_bundle"]
                self.assertEqual(full["canonical"]["triple_count"], 928)
                accounting = next(g for g in full["gates"] if g["gate"] == "no-omission")
                self.assertEqual(accounting["evidence"]["dispositions"]["HELD"], 31)

            self.assertEqual(semantic_receipt(first), semantic_receipt(second))
            self.assertEqual(tree_hashes(fixture), before)

    def test_excerpt_pin_mismatch_blocks_before_semantic_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = copy_fixture(root / "fixture")
            good = run_fixture(REPO, str(PYTHON), FIXTURE / "descriptor.json", root / "good")
            self.assertEqual(good["status"], "SUCCEEDED")
            prior = tree_hashes(root / "good")
            excerpt = fixture / "source.html"
            excerpt.write_bytes(excerpt.read_bytes() + b" ")
            before = tree_hashes(fixture)

            result = run_fixture(REPO, str(PYTHON), fixture / "descriptor.json", root / "run")

            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["failed_stage"], "source_fixture")
            self.assertIn("EXCERPT", result["error_code"])
            self.assertIsNone(result["semantic_result"])
            self.assertIsNone(result["graph_result"])
            self.assertEqual(tree_hashes(fixture), before)
            self.assertEqual(tree_hashes(root / "good"), prior)
            retry = run_fixture(REPO, str(PYTHON), FIXTURE / "descriptor.json", root / "retry")
            self.assertEqual(semantic_receipt(retry), semantic_receipt(good))
            self.assertEqual(tree_hashes(root / "good"), prior)

    def test_semantic_foreign_key_failure_preserves_fixture_and_skips_graph(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = copy_fixture(root / "fixture")
            descriptor_path = fixture / "descriptor.json"
            descriptor = json.loads(descriptor_path.read_text())
            assertions_path = fixture / "csv" / "source_assertions.csv"
            with assertions_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
                fields = list(rows[0])
            rows[0]["source_id"] = "UNKNOWN-FIXTURE-SOURCE"
            with assertions_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            descriptor["seed_csv"]["source_assertions.csv"] = sha(assertions_path)
            descriptor_path.write_text(json.dumps(descriptor, ensure_ascii=False, sort_keys=True,
                                                  indent=2) + "\n", encoding="utf-8")
            before = tree_hashes(fixture)

            result = run_fixture(REPO, str(PYTHON), descriptor_path, root / "run")

            self.assertEqual(result["status"], "BLOCKED", result)
            self.assertEqual(result["failed_stage"], "source_fixture")
            self.assertIsNone(result["semantic_result"])
            self.assertIsNone(result["graph_result"])
            self.assertIn("RELATIONAL_VALIDATION_FAILED", result["error_code"])
            self.assertEqual(tree_hashes(fixture), before)

    def test_fixture_cannot_claim_production_scope_or_overwrite_good_output(self):
        from lib.ithkuil.src.ingestion_semantic import run_semantic
        from lib.ithkuil.src.ingestion import _bytes, _sha
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            good = run_fixture(REPO, str(PYTHON), FIXTURE / "descriptor.json", root / "good")
            self.assertEqual(good["status"], "SUCCEEDED")
            prior = tree_hashes(root / "good")
            refused = run_fixture(REPO, str(PYTHON), FIXTURE / "descriptor.json", root / "good")
            self.assertEqual(refused["status"], "BLOCKED")
            self.assertEqual(tree_hashes(root / "good"), prior)
            source = good["source_result"]
            frontier = Path(source["frontier"]["path"])
            value = json.loads(frontier.read_text())
            value["claims"]["production_admission"] = True
            value.pop("receipt_sha256")
            value["receipt_sha256"] = _sha(_bytes(value))
            frontier.write_bytes(_bytes(value))
            failed = run_semantic(REPO, str(PYTHON), frontier.parent.parent,
                                  frontier, root / "forbidden")
            self.assertEqual(failed["error_code"], "FIXTURE_FRONTIER_CLAIMS_INVALID")
            self.assertFalse((root / "forbidden").exists())

    def test_conformance_failure_preserves_source_and_prior_good_artifacts(self):
        from lib.ithkuil.src.ingestion_semantic import run_semantic
        from lib.ithkuil.tests.ingestion_failure_injection import fail_no_omission
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            good = run_fixture(REPO, str(PYTHON), FIXTURE / "descriptor.json", root / "good")
            self.assertEqual(good["status"], "SUCCEEDED", good.get("error_code"))
            before = tree_hashes(root / "good")
            source = good["source_result"]
            data = Path(source["artifacts"]["canonical_root"]) / "_data/csv"
            failed = run_semantic(REPO, str(PYTHON), data, source["frontier"]["path"],
                                  root / "failed", source_result=source,
                                  command_runner=fail_no_omission)
            self.assertEqual(failed["status"], "FAILED", failed.get("error_code"))
            self.assertEqual(failed["failed_gates"], ["no-omission"])
            self.assertFalse(failed["graph_eligibility"]["eligible"])
            self.assertEqual(tree_hashes(root / "good"), before)
            retried = run_semantic(REPO, str(PYTHON), data, source["frontier"]["path"],
                                   root / "retry", source_result=source)
            self.assertEqual(retried["status"], "SUCCEEDED", retried.get("error_code"))
            self.assertEqual(retried["artifacts"]["full_conformance_bundle"]["bundle_id"],
                             good["semantic_result"]["artifacts"]["full_conformance_bundle"]["bundle_id"])
            self.assertEqual(tree_hashes(root / "good"), before)

    def test_required_unavailable_graph_preserves_successful_semantic_artifacts(self):
        from lib.ithkuil.src.ingestion_graph import run_graph
        from lib.ithkuil.src.skos.falkor_smoke import SUITE_PATH

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = copy_fixture(root / "fixture")
            result = run_fixture(REPO, str(PYTHON), fixture / "descriptor.json", root / "run")
            self.assertEqual(result["status"], "SUCCEEDED", result)
            semantic = result["semantic_result"]
            core_path = Path(semantic["artifacts"]["core_generation_bundle"]["canonical"]["path"])
            full_path = Path(semantic["artifacts"]["full_conformance_bundle"]["canonical"]["path"])
            before = (sha(core_path), sha(full_path), tree_hashes(fixture))

            graph = run_graph(
                REPO, PYTHON, semantic, root / "graph-failure", enabled=True, required=True,
                graph="bilqis_skos_19_91_unreachable_fixture", owner="codex_ingestion_91",
                host="127.0.0.1", port=1, suite=SUITE_PATH,
                notation="∅", datatype="A", expected_iri="https://www.ithkuil.net/",
            )

            self.assertEqual(graph["status"], "FAILED", graph)
            self.assertEqual(graph["failed_stage"], "runtime_preflight")
            self.assertEqual((sha(core_path), sha(full_path), tree_hashes(fixture)), before)


if __name__ == "__main__":
    unittest.main()
