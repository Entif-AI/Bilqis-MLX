import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from lib.ithkuil.src.skos.build import PROFILE_VERSION, build, compile_corpus
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.publication import publish_bundle, verify_publication


LIB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = LIB_ROOT.parents[1]
SOURCE = LIB_ROOT / "_data/csv"


class ReproducibleBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = compile_corpus(SOURCE)

    def code(self, expected, function, *args, **kwargs):
        with self.assertRaises(ProfileError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, expected)

    def cli(self, source, output, *, cwd=None, seed="9", profile=PROFILE_VERSION):
        return subprocess.run(
            [sys.executable, "-B", "-m", "lib.ithkuil.src.skos.build", "--input-root", str(source),
             "--output-root", str(output), "--profile", profile],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90,
            cwd=cwd or REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT), "PYTHONHASHSEED": seed},
        )

    def test_current_core_is_complete_accounting_of_a_partial_semantic_projection(self):
        metadata = self.bundle.metadata()
        self.assertEqual(metadata["status"], "partial")
        self.assertTrue(metadata["release_ineligible"])
        self.assertEqual(metadata["emitted_resources"], 2579)
        self.assertEqual(metadata["resolved_resources"], 2968)
        self.assertEqual(metadata["triple_count"], 19489)
        self.assertEqual(set(dict(self.bundle.files)), {"canonical.nt", "held.json", "digest.json", "input.json"})
        ledger = json.loads(dict(self.bundle.files)["held.json"])
        self.assertFalse(ledger["blocking"])
        self.assertEqual(ledger["counts"]["by_status"], {
            "EMITTED": 2590, "HELD": 500, "REJECTED": 0, "UNSUPPORTED": 1917, "IR_ONLY": 5581,
        })
        digest = json.loads(dict(self.bundle.files)["digest.json"])
        self.assertEqual(digest["sha256"], metadata["canonical_sha256"])
        self.assertEqual(digest["profile_sha256"], metadata["profile_sha256"])
        self.assertEqual(digest["input_closure_sha256"], metadata["input_closure_sha256"])
        self.assertEqual(digest["compiler"]["sha256"], metadata["compiler_sha256"])

    def test_repeat_compile_produces_exactly_equal_complete_bundle(self):
        again = compile_corpus(SOURCE)
        self.assertEqual(again, self.bundle)
        self.assertEqual(again.bundle_id, self.bundle.bundle_id)

    def test_fresh_csv_only_workspaces_reordered_rows_and_processes_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "csv"
            shutil.copytree(SOURCE, source)
            first = self.cli(source, root / "one", cwd=root, seed="11")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stderr, "")
            first_receipt = json.loads(first.stdout)
            self.assertEqual(first_receipt["bundle_id"], self.bundle.bundle_id)
            self.assertFalse((root / "_private").exists())
            for path in source.rglob("*.csv"):
                with path.open(newline="", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    fields, rows = reader.fieldnames, list(reader)
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(reversed(fields)))
                    writer.writeheader()
                    writer.writerows(reversed(rows))
            second = self.cli(source, root / "two", cwd=root, seed="73")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stderr, "")
            self.assertEqual(json.loads(second.stdout)["bundle_id"], first_receipt["bundle_id"])
            first_dir = root / "one" / first_receipt["generation"]
            second_dir = root / "two" / json.loads(second.stdout)["generation"]
            self.assertEqual({path.name: path.read_bytes() for path in first_dir.iterdir()},
                             {path.name: path.read_bytes() for path in second_dir.iterdir()})
            self.assertEqual(verify_publication(root / "two")["bundle_id"], self.bundle.bundle_id)

    def test_blocking_preflight_writes_no_new_output_and_keeps_previous_valid_pointer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "csv"
            shutil.copytree(SOURCE, source)
            (source / "morphemes_atomic.csv").unlink()
            result = self.cli(source, root / "new-output", cwd=root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            error = json.loads(result.stderr)
            self.assertEqual(error["status"], "blocked")
            self.assertIn("MISSING_TABLE", json.dumps(error))
            self.assertFalse((root / "new-output").exists())
            old = root / "existing-output"
            publish_bundle(self.bundle, old)
            pointer = (old / "CURRENT.json").read_bytes()
            failed = self.cli(source, old, cwd=root)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual((old / "CURRENT.json").read_bytes(), pointer)
            self.assertEqual(verify_publication(old)["bundle_id"], self.bundle.bundle_id)

    def test_unknown_profile_and_output_inside_source_are_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            self.code("UNSUPPORTED_COMPILER_PROFILE", compile_corpus, SOURCE, profile_version="unknown/2")
            result = self.cli(SOURCE, output, profile="unknown/2")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stderr)["code"], "UNSUPPORTED_COMPILER_PROFILE")
            self.assertFalse(output.exists())
            self.code("OUTPUT_INSIDE_SOURCE_ROOT", build, SOURCE, SOURCE / "build-output")
            self.assertFalse((SOURCE / "build-output").exists())
            self.code("OUTPUT_INSIDE_COMPILER_SOURCE", build, SOURCE, LIB_ROOT / "src/skos/output")
            self.assertFalse((LIB_ROOT / "src/skos/output").exists())
            alias = Path(temporary) / "alias"
            alias.symlink_to(Path(temporary), target_is_directory=True)
            self.code("OUTPUT_ROOT_SYMLINK_FORBIDDEN", build, SOURCE, alias)

    def test_artifact_bytes_have_no_workstation_paths_or_wall_clock_timestamp(self):
        forbidden = (str(REPO_ROOT).encode(), b"/Users/", b"/home/", b"created_at", b"built_at")
        for name, payload in (*self.bundle.files, ("manifest.json", self.bundle.manifest)):
            with self.subTest(file=name):
                for marker in forbidden:
                    self.assertNotIn(marker, payload)
        inputs = json.loads(dict(self.bundle.files)["input.json"])
        self.assertEqual(inputs["normalization"], "exact-values-sorted-json-rows/v1")
        self.assertEqual(set(inputs["tables"]), {
            "source_manifest", "curriculum_manifest", "source_sections", "source_tables",
            "source_assertions", "grammatical_categories", "morphemes_atomic", "root_senses",
            "lexicon_roots", "lexicon_root_senses", "lexicon_root_evidence", "morpheme_compositions",
        })


if __name__ == "__main__":
    unittest.main()
