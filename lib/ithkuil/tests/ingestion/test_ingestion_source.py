from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lib.ithkuil.src.ingestion import run_source


REPO = REPO_ROOT
ITHKUIL = REPO / "lib" / "ithkuil"
PYTHON = REPO / ".venv" / "bin" / "python"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_hashes(ithkuil: Path) -> dict[str, str]:
    data = ithkuil / "_data/csv"
    paths = list(data.glob("*.csv"))
    sources = data / "sources"
    paths.extend(sources.glob("*.json"))
    paths.extend((sources / "lexicon_frontier").glob("chapter-*-accounting.json"))
    summary = ithkuil / "EXTRACTION_FRONTIER.md"
    if summary.is_file():
        paths.append(summary)
    return {path.relative_to(ithkuil).as_posix(): digest(path) for path in paths}


def copied_repo(parent: Path) -> Path:
    root = parent / "repo"
    root.mkdir()
    shutil.copytree(
        ITHKUIL,
        root / "lib" / "ithkuil",
        ignore=shutil.ignore_patterns("_raw", "_private", ".local", "__pycache__", "*.pyc"),
    )
    manifest = root / "lib/ithkuil/_data/csv/sources/source_manifest.csv"
    with manifest.open(encoding="utf-8", newline="") as stream:
        names = [row["local_name"] for row in csv.DictReader(stream)]
    raw = root / "lib/ithkuil/_raw"
    raw.mkdir()
    for name in names:
        shutil.copy2(ITHKUIL / "_raw" / name, raw / name)
    return root


class SourceIngestionTests(unittest.TestCase):
    def test_bounded_affix_uses_real_owners_and_publishes_verified_frontier(self):
        with tempfile.TemporaryDirectory(dir=REPO) as temporary:
            root = copied_repo(Path(temporary))
            result = run_source(root, str(PYTHON), selection="affix")

            details = result
            if result["status"] != "SUCCEEDED" and result["commands"]:
                details = dict(result)
                details["stderr"] = Path(result["commands"][-1]["stderr_log_ref"]).read_text()
            self.assertEqual(result["status"], "SUCCEEDED", details)
            self.assertEqual(result["failed_stage"], None)
            self.assertEqual(
                [command["stage"] for command in result["commands"]],
                ["build_structure", "validate_dataset", "source_frontier"],
            )
            self.assertTrue(result["validator"]["passed"])
            frontier = root / "lib/ithkuil/_data/csv/sources/extraction_frontier.json"
            self.assertEqual(result["frontier"]["sha256"], digest(frontier))
            self.assertEqual(result["frontier"]["entry_count"], 26)
            self.assertTrue(result["debt"])
            self.assertEqual(result["artifacts"]["readback_verified"], True)
            published_hashes = result["artifacts"]["published_artifact_hashes"]
            source_tables = root / "lib/ithkuil/_data/csv/source_tables.csv"
            self.assertEqual(published_hashes["_data/csv/source_tables.csv"], digest(source_tables))
            self.assertEqual(result["artifacts"]["canonical_root"], str(root / "lib/ithkuil"))
            self.assertTrue(result["source_manifest_sha256"])
            self.assertFalse(any("skos.build" in " ".join(c["argv"]) for c in result["commands"]))
            self.assertFalse(any("skos.conformance" in " ".join(c["argv"]) for c in result["commands"]))

            reused = run_source(root, str(PYTHON), selection="affix")
            self.assertEqual(reused["status"], "REUSED", reused)
            self.assertEqual(reused["artifacts"]["canonical_root"], result["artifacts"]["canonical_root"])
            self.assertEqual(reused["artifacts"]["published_artifact_hashes"], published_hashes)
            self.assertEqual([command["stage"] for command in reused["commands"]],
                             ["validate_dataset", "source_frontier_check"])

            def drift_during_revalidation(argv, cwd, env, timeout):
                target = root / "lib/ithkuil/_data/csv/morphemes_atomic.csv"
                with target.open("ab") as stream:
                    stream.write(b"\n")
                return {"exit_code": 0, "stdout": "", "stderr": ""}

            drifted = run_source(root, str(PYTHON), selection="affix",
                                 command_runner=drift_during_revalidation)
            self.assertEqual(drifted["status"], "FAILED")
            self.assertEqual(drifted["error_code"], "CACHE_IDENTITY_CHANGED")
            self.assertEqual(json.loads(Path(drifted["run_record"]).read_text())["status"], "FAILED")

    def test_source_pin_mismatch_stops_before_commands_and_preserves_csvs(self):
        with tempfile.TemporaryDirectory(dir=REPO) as temporary:
            root = copied_repo(Path(temporary))
            data = root / "lib/ithkuil/_data/csv"
            before = artifact_hashes(root / "lib/ithkuil")
            manifest = data / "sources/source_manifest.csv"
            with manifest.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0]["sha256"] = "0" * 64
            with manifest.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)

            result = run_source(root, str(PYTHON), selection="affix")

            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["failed_stage"], "inspect")
            self.assertEqual(result["commands"], [])
            self.assertEqual(before, artifact_hashes(root / "lib/ithkuil"))

    def test_owner_failure_keeps_canonical_baseline_untouched(self):
        with tempfile.TemporaryDirectory(dir=REPO) as temporary:
            root = copied_repo(Path(temporary))
            data = root / "lib/ithkuil/_data/csv"
            before = artifact_hashes(root / "lib/ithkuil")

            def fail_owner(argv, cwd, env, timeout):
                return {"exit_code": 23, "stdout": "", "stderr": "fixture failure"}

            result = run_source(root, str(PYTHON), selection="affix", command_runner=fail_owner)

            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["failed_stage"], "build_structure")
            self.assertEqual(result["commands"][0]["exit_code"], 23)
            self.assertEqual(before, artifact_hashes(root / "lib/ithkuil"))
            run_record = json.loads(Path(result["run_record"]).read_text(encoding="utf-8"))
            self.assertEqual(run_record["status"], "FAILED")

            # A crash after entering publication must not silently start attempt 2.
            run_record["status"] = "PUBLISHING"
            run_record["active_stage"] = "publish"
            record_path = Path(result["run_record"])
            record_path.write_text(json.dumps(run_record, sort_keys=True, separators=(",", ":")) + "\n",
                                   encoding="utf-8")
            prior_bytes = record_path.read_bytes()
            recovery = run_source(root, str(PYTHON), selection="affix", command_runner=fail_owner)
            self.assertEqual(recovery["status"], "RECONCILE_REQUIRED")
            self.assertEqual(recovery["error_code"], "PRIOR_ATTEMPT_REQUIRES_RECONCILIATION")
            self.assertEqual(recovery["commands"], [])
            self.assertEqual(record_path.read_bytes(), prior_bytes)
            self.assertEqual(sorted(path.name for path in record_path.parent.glob("attempt-*")),
                             ["attempt-001"])

    def test_unsupported_selection_returns_typed_stop_without_side_effects(self):
        result = run_source(REPO, str(PYTHON), selection="semantic")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["error_code"], "SELECTION_UNSUPPORTED")
        self.assertEqual(result["commands"], [])


if __name__ == "__main__":
    unittest.main()
