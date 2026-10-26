from __future__ import annotations

from lib.ithkuil.tests.source_expectations import LEXICON

import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import json


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "src" / "build_curriculum_frontier.py"
DATA = ROOT / "_data" / "csv"

LIVE_A_B_C = {
    "A.IDENTITY",
    "A.PARENT",
    "A.EDGE",
    "A.LINK",
    "A.MEMBER",
    "A.MAPS",
    "B.AND",
    "B.IFF",
    "B.COMPOSITE",
    "B.IDBOOLOPS",
    "C.COUNT",
    "C.NUMBER",
    "C.SUCCESSOR",
    "C.ADD",
    "C.SUB",
    "C.MUL",
    "C.DIV",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class CurriculumFrontierTest(unittest.TestCase):
    def test_abi_anchor_matching_is_exact_bridge_identity(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("frontier_builder", BUILDER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.crosswalk[:] = [
            {"new_ithkuil_bridge": "-AB-", "bilqis_token_id": "1", "bilqis_token_symbol": "x", "mapping_disposition": "ok"},
            {"new_ithkuil_bridge": "prefix-AB-suffix", "bilqis_token_id": "2", "bilqis_token_symbol": "y", "mapping_disposition": "wrong"},
        ]
        self.assertEqual(module.anchor_rows("-AB-"), ["1:x:ok"])

    def test_frontier_manifest_records_and_validates_inputs_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env["BILQIS_CURRICULUM_FRONTIER_OUT"] = temp
            subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, env=env, check=True)
            manifest_path = Path(temp) / "frontier_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], "bilqis.ithkuil.frontier-manifest/v1")
            self.assertEqual(len(manifest["input_files"]), 4)
            self.assertIn("candidate_pool.csv", manifest["output_files"])
            import importlib.util
            spec = importlib.util.spec_from_file_location("frontier_manifest_builder", BUILDER)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.validate_frontier_manifest(manifest_path)["output_digest"], manifest["output_digest"])
            (Path(temp) / "candidate_pool.csv").write_text("stale\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "OUTPUT_STALE:candidate_pool.csv"):
                module.validate_frontier_manifest(manifest_path)

    def test_frontier_manifest_validator_rejects_missing_output_and_bad_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env["BILQIS_CURRICULUM_FRONTIER_OUT"] = temp
            subprocess.run(
                [sys.executable, str(BUILDER)], cwd=ROOT, env=env, check=True)
            manifest_path = Path(temp) / "frontier_manifest.json"
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "frontier_manifest_strict_builder", BUILDER)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["output_files"].pop("candidate_pool.csv")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "OUTPUT_SET_INVALID"):
                module.validate_frontier_manifest(manifest_path)
            subprocess.run(
                [sys.executable, str(BUILDER)], cwd=ROOT, env=env, check=True)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["output_digest"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "OUTPUT_DIGEST_INVALID"):
                module.validate_frontier_manifest(manifest_path)

    def test_research_frontier_is_source_explicit_and_dependency_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env["BILQIS_CURRICULUM_FRONTIER_OUT"] = temp
            subprocess.run(
                [sys.executable, str(BUILDER)],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            out = Path(temp)
            grade_map = read_csv(out / "grade_map.csv")
            candidates = read_csv(out / "candidate_pool.csv")
            senses = read_csv(out / "sense_candidate_pool.csv")
            inventory = read_csv(out / "source_inventory.csv")
            deferred = read_csv(out / "deferred_codec.csv")

        self.assertEqual(len(grade_map), 144)
        self.assertEqual(len(candidates), 240)
        self.assertEqual(
            sum(row["priority_tier"] == "NEXT_96" for row in candidates), 96
        )
        self.assertEqual(len(senses), LEXICON["sense_rows"])
        self.assertEqual(len(inventory), LEXICON["root_rows"])
        self.assertEqual(len(deferred), 36)

        self.assertEqual(
            {row["grade"] for row in grade_map},
            set("DEFGHIJKLMNO"),
        )
        for grade in "DEFGHIJKLMNO":
            self.assertEqual(
                sum(row["grade"] == grade for row in grade_map),
                12,
                grade,
            )

        target_ids = [row["target_sense_id"] for row in grade_map]
        self.assertEqual(len(set(target_ids)), 144)
        self.assertTrue(
            all(
                row["target_sense_id"]
                and row["target_stem"] is not None
                and row["target_specification"]
                and row["target_source_sense"]
                for row in grade_map
            )
        )
        self.assertTrue(
            all(
                row["answer_family"] and row["minimal_world_state"]
                for row in grade_map
            )
        )

        canonical_senses = {
            row["lexicon_sense_id"]: row
            for row in read_csv(DATA / "lexicon_root_senses.csv")
        }
        for row in grade_map:
            source = canonical_senses[row["target_sense_id"]]
            self.assertEqual(source["root_form_raw"], row["root_form"])
            self.assertEqual(source["stem"], row["target_stem"])
            self.assertEqual(source["specification"], row["target_specification"])
            self.assertEqual(source["sense_summary"], row["target_source_sense"])

        seen = set(LIVE_A_B_C)
        for row in grade_map:
            capability = row["working_capability"]
            for prerequisite in filter(
                None, (part.strip() for part in row["prerequisites"].split(";"))
            ):
                self.assertIn(
                    prerequisite,
                    seen,
                    f"{capability} has unavailable prerequisite {prerequisite}",
                )
            seen.add(capability)

        forbidden = {"B.NOT", "B.OR", "B.XOR", "B.IMPLIES"}
        self.assertTrue(
            all(
                prerequisite not in forbidden
                for row in grade_map
                for prerequisite in (
                    part.strip() for part in row["prerequisites"].split(";")
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
