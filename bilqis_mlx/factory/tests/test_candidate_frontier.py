import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import csv

from bilqis_mlx.factory.candidate_frontier import (
    CandidateFrontierRelease,
    PrerequisiteStatus,
    load_candidate_frontier,
)


ROOT = Path(__file__).resolve().parents[3]
BUILDER = ROOT / "lib/ithkuil/src/build_curriculum_frontier.py"
SOURCE = ROOT / "lib/ithkuil/_data/csv"
OUTPUT_NAMES = (
    "candidate_pool.csv", "grade_map.csv", "sense_candidate_pool.csv",
    "source_inventory.csv", "deferred_codec.csv", "grade_rationale.csv",
    "frontier_plan.json",
)
INPUT_NAMES = (
    "lexicon_roots.csv", "lexicon_root_senses.csv", "lexicon_root_evidence.csv",
    "bilqis_ithkuil_crosswalk.csv",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_output_hashes(artifact_dir):
    manifest_path = artifact_dir / "frontier_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = {name: sha256(artifact_dir / name) for name in OUTPUT_NAMES}
    manifest["output_files"] = outputs
    manifest["output_digest"] = hashlib.sha256("".join(
        f"{name}:{digest}\n" for name, digest in sorted(outputs.items())).encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def refresh_input_hashes(artifact_dir, source_dir):
    manifest_path = artifact_dir / "frontier_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inputs = {name: sha256(source_dir / name) for name in INPUT_NAMES}
    manifest["input_files"] = inputs
    manifest["input_digest"] = hashlib.sha256("".join(
        f"{name}:{digest}\n" for name, digest in sorted(inputs.items())).encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


class CandidateFrontierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "artifacts"
        self.source = self.root / "source"
        shutil.copytree(SOURCE, self.source)
        environment = {**os.environ, "BILQIS_CURRICULUM_FRONTIER_OUT": str(self.artifacts)}
        subprocess.run([sys.executable, str(BUILDER)], check=True, env=environment,
                       capture_output=True, text=True)
        self.builder_sha256 = sha256(BUILDER)

    def load(self):
        return load_candidate_frontier(
            self.artifacts, self.source,
            expected_builder_sha256=self.builder_sha256)

    def test_loads_full_source_pool_with_selected_and_reserve_provenance(self):
        frontier = self.load()
        self.assertEqual(len(frontier.senses), 1615)
        self.assertEqual(len(frontier.candidates), 240)
        selected = [item for item in frontier.candidates
                    if item.priority_tier == "CORE_D_O"]
        reserve = [item for item in frontier.candidates
                   if item.priority_tier == "NEXT_96"]
        self.assertEqual(len(selected), 144)
        self.assertEqual(len(reserve), 96)
        self.assertTrue(all(item.target_sense_id for item in selected))
        self.assertTrue(all(not item.target_sense_id for item in reserve))
        self.assertTrue(all(
            edge.status is PrerequisiteStatus.HYPOTHESIS
            for item in frontier.candidates for edge in item.prerequisites))
        self.assertIn("FACTORY_ADMISSION_REQUIRED", selected[0].readiness_debt)

    def test_roundtrip_manifest_is_content_addressed(self):
        frontier = self.load()
        restored = CandidateFrontierRelease.from_manifest(
            json.loads(json.dumps(frontier.manifest())), frontier.release_sha256)
        self.assertEqual(restored, frontier)

    def test_roundtrip_rejects_candidate_that_claims_admission(self):
        frontier = self.load()
        manifest = json.loads(json.dumps(frontier.manifest()))
        manifest["candidates"][0]["disposition"] = "ADMITTED"
        with self.assertRaisesRegex(
                ValueError, "CANDIDATE_FRONTIER_MANIFEST_INVALID"):
            CandidateFrontierRelease.from_manifest(
                manifest, frontier.release_sha256)

    def test_stale_builder_input_and_output_hashes_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "BUILDER_STALE"):
            load_candidate_frontier(
                self.artifacts, self.source,
                expected_builder_sha256="f" * 64)
        (self.source / "lexicon_roots.csv").write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "INPUT_STALE"):
            self.load()

    def test_output_mutation_fails_before_frontier_interpretation(self):
        with (self.artifacts / "candidate_pool.csv").open("a", encoding="utf-8") as handle:
            handle.write("\n")
        with self.assertRaisesRegex(ValueError, "OUTPUT_STALE"):
            self.load()

    def test_mutated_sense_identity_fails_against_hash_bound_lexicon(self):
        path = self.artifacts / "sense_candidate_pool.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = tuple(rows[0])
        rows[0]["root_form"] = "-MUTATED-"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        refresh_output_hashes(self.artifacts)
        with self.assertRaisesRegex(ValueError, "SENSE_SOURCE_MISMATCH"):
            self.load()

    def test_prerequisite_rationale_cannot_be_relabelled_as_admission(self):
        frontier = self.load()
        manifest = frontier.manifest()
        manifest["candidates"][0]["prerequisites"][0]["status"] = "ADMITTED"
        with self.assertRaisesRegex(ValueError, "MANIFEST_INVALID"):
            CandidateFrontierRelease.from_manifest(manifest, frontier.release_sha256)

    def test_future_source_sense_is_accepted_when_the_sidecar_is_rebound(self):
        """Expansion is valid when every generated/source identity is rebound."""
        sense_path = self.source / "lexicon_root_senses.csv"
        artifact_path = self.artifacts / "sense_candidate_pool.csv"
        with artifact_path.open(encoding="utf-8", newline="") as handle:
            artifact_rows = list(csv.DictReader(handle))
            artifact_fields = tuple(artifact_rows[0])
        seed = next(item for item in artifact_rows
                    if not item["selected_target_capability"])
        new_id = "LEXSENSE-future-source-bound"
        future_artifact = {**seed, "lexicon_sense_id": new_id,
                           "semantic_disposition": "VISIBLE_FUTURE_CANDIDATE"}
        artifact_rows.append(future_artifact)
        with artifact_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=artifact_fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(artifact_rows)

        with sense_path.open(encoding="utf-8", newline="") as handle:
            source_rows = list(csv.DictReader(handle))
            source_fields = tuple(source_rows[0])
        source_seed = next(item for item in source_rows
                           if item["lexicon_sense_id"] == seed["lexicon_sense_id"])
        source_rows.append({**source_seed, "lexicon_sense_id": new_id})
        with sense_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=source_fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(source_rows)
        refresh_input_hashes(self.artifacts, self.source)
        refresh_output_hashes(self.artifacts)

        frontier = self.load()
        self.assertEqual(len(frontier.senses), 1616)


if __name__ == "__main__":
    unittest.main()
