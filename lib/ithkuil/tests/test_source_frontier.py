import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from lib.ithkuil.src.source_frontier import generate, render_markdown


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data" / "csv"
PINS = ROOT / "src" / "lexicon_frontier_pins.json"


def _entry(receipt, source_id, artifact_id=None):
    return next(
        item for item in receipt["entries"]
        if item["source_id"] == source_id
        and (artifact_id is None or item["artifact_id"] == artifact_id)
    )


def _csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path, rows):
    columns = list(rows[0]) if rows else next(csv.reader(path.open(encoding="utf-8", newline="")))
    path.unlink()
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _copied_data(tmp_path):
    ithkuil = tmp_path / "lib" / "ithkuil"
    data_root = ithkuil / "_data" / "csv"
    data_root.parent.mkdir(parents=True)
    shutil.copytree(DATA, data_root)
    (ithkuil / "_raw").symlink_to(ROOT / "_raw", target_is_directory=True)
    (data_root.parent / "pdf").symlink_to(ROOT / "_data" / "pdf", target_is_directory=True)
    return data_root


class SourceFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = generate(data_root=DATA, pins_path=PINS)

    def test_current_frontier_has_literal_counts_and_truthful_boundaries(self):
        receipt = self.receipt
        aggregates = receipt["aggregates"]

        self.assertEqual(receipt["reconciliation"], {
            "source_manifest_entries": 18,
            "split_chapter_entries": 8,
            "entry_count": 26,
        })
        self.assertEqual(aggregates["lexicon"]["roots"], 5810)
        self.assertEqual(aggregates["lexicon"]["senses"], 3008)
        self.assertEqual(aggregates["lexicon"]["evidence"], 9488)
        self.assertEqual(aggregates["lexicon"]["roots_without_parsed_senses"], 5097)
        self.assertEqual(aggregates["affix"]["parsed_tables"], 403)
        self.assertEqual(aggregates["affix"]["parsed_cells"], 8060)
        self.assertEqual(aggregates["affix"]["unsupported_tables"], 35)
        self.assertEqual(aggregates["affix"]["conflicting_tables"], 2)
        self.assertEqual(receipt["claims"], {
            "full_new_ithkuil_coverage": False,
            "semantic_admission": False,
            "curriculum_admission": False,
        })
        self.assertEqual(aggregates["debt"]["by_reason"]["legacy_debt_not_measured"], 2)

        self.assertEqual(_entry(receipt, "NI-WEB-INDEX")["status"], "PINNED_UNPARSED")
        self.assertEqual(_entry(receipt, "NI-LEXICON-SITE")["status"], "PINNED_UNPARSED")
        self.assertEqual(_entry(receipt, "NI-LEXICON-CURRICULUM", "NI-LEXICON-CURRICULUM:CHAPTER:0")["status"], "PINNED_UNPARSED")
        self.assertEqual(_entry(receipt, "NI-LEXICON-CURRICULUM", "NI-LEXICON-CURRICULUM:CHAPTER:1")["debt_by_reason"]["legacy_debt_not_measured"], 1)
        self.assertEqual(_entry(receipt, "NI-LEXICON-CURRICULUM", "NI-LEXICON-CURRICULUM:CHAPTER:2")["debt_by_reason"]["legacy_debt_not_measured"], 1)
        self.assertEqual(_entry(receipt, "NI-LEXICON-CURRICULUM", "NI-LEXICON-CURRICULUM:CHAPTER:3")["status"], "PARSED_WITH_DEBT")
        self.assertFalse(aggregates["grammar"]["semantic_exhaustiveness_measured"])

        schema = json.loads((ROOT / "src" / "source_frontier.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(receipt)), [])
        invalid = json.loads(json.dumps(receipt))
        invalid["entries"][0]["status"] = "GUESSED_COMPLETE"
        self.assertTrue(list(validator.iter_errors(invalid)))
        invalid = json.loads(json.dumps(receipt))
        invalid['entries'].pop()
        self.assertTrue(list(validator.iter_errors(invalid)))
        unsigned = dict(receipt)
        expected_digest = unsigned.pop('receipt_sha256')
        self.assertEqual(hashlib.sha256(_json_bytes(unsigned)).hexdigest(), expected_digest)
        self.assertEqual(receipt['aggregates']['debt']['by_reason']['legacy_debt_not_measured'], 2)

        markdown = render_markdown(receipt)
        self.assertIn("Full New Ithkuil coverage: no", markdown)
        self.assertIn("Semantic admission: no", markdown)
        self.assertIn("Curriculum admission: no", markdown)
        self.assertIn("| unsupported_table_shape | 35 |", markdown)

    def test_frontier_receipt_and_markdown_are_repeatable(self):
        first = generate(data_root=DATA, pins_path=PINS)
        second = generate(data_root=DATA, pins_path=PINS)
        self.assertEqual(_json_bytes(first), _json_bytes(second))
        self.assertEqual(render_markdown(first).encode(), render_markdown(second).encode())

    def test_receipt_tracks_four_source_frontier_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            data_root = _copied_data(Path(temp))
            sources = data_root / "sources"
            baseline = generate(data_root=data_root, pins_path=PINS)

            manifest_path = sources / "source_manifest.csv"
            manifest_bytes = manifest_path.read_bytes()
            manifest_rows = _csv_rows(manifest_path)
            row = next(row for row in manifest_rows if row["source_id"] == "NI-WEB-CH01")
            row["sha256"] = "0" * 64
            _write_csv(manifest_path, manifest_rows)
            drifted = generate(data_root=data_root, pins_path=PINS)
            self.assertEqual(_entry(drifted, "NI-WEB-CH01")["status"], "BLOCKED_SOURCE_IDENTITY")
            self.assertNotEqual(drifted["receipt_sha256"], baseline["receipt_sha256"])
            manifest_path.write_bytes(manifest_bytes)

            profile_path = sources / "lexicon_frontier_manifest.json"
            profile_bytes = profile_path.read_bytes()
            accounting_path = sources / "lexicon_frontier" / "chapter-3-accounting.json"
            accounting_bytes = accounting_path.read_bytes()
            accounting = json.loads(accounting_bytes)
            accounting.append({"status": "DEBT_UNSUPPORTED_SHAPE"})
            accounting_path.write_bytes(_json_bytes(accounting))
            profile = json.loads(profile_bytes)
            chapter = profile["chapter_receipts"]["3"]
            chapter["accounting_sha256"] = hashlib.sha256(accounting_path.read_bytes()).hexdigest()
            chapter["dispositions"]["DEBT_UNSUPPORTED_SHAPE"] += 1
            chapter["counts"]["source_observations"] += 1
            profile_path.write_bytes(_json_bytes(profile))
            indebted = generate(data_root=data_root, pins_path=PINS)
            debt = _entry(indebted, "NI-LEXICON-CURRICULUM", "NI-LEXICON-CURRICULUM:CHAPTER:3")["debt_by_reason"]
            base_debt = _entry(baseline, "NI-LEXICON-CURRICULUM", "NI-LEXICON-CURRICULUM:CHAPTER:3")["debt_by_reason"]
            self.assertEqual(debt["DEBT_UNSUPPORTED_SHAPE"], base_debt["DEBT_UNSUPPORTED_SHAPE"] + 1)
            self.assertNotEqual(indebted["receipt_sha256"], baseline["receipt_sha256"])
            profile_path.write_bytes(profile_bytes)
            accounting_path.write_bytes(accounting_bytes)

            sections_path = data_root / "source_sections.csv"
            sections_bytes = sections_path.read_bytes()
            sections = _csv_rows(sections_path)
            sections.append({
                "section_id": "NI-WEB-INDEX:S001", "source_id": "NI-WEB-INDEX",
                "chapter_number": "", "chapter_title": "", "section_number": "1",
                "section_title": "Index section", "source_heading_text": "Index section",
                "hierarchy_depth": "1", "parent_section_id": "", "source_anchor": "",
                "source_url": "https://www.ithkuil.net/", "source_line": "1",
            })
            _write_csv(sections_path, sections)
            newly_parsed = generate(data_root=data_root, pins_path=PINS)
            self.assertEqual(_entry(newly_parsed, "NI-WEB-INDEX")["status"], "PARSED_WITH_DEBT")
            self.assertNotEqual(newly_parsed["receipt_sha256"], baseline["receipt_sha256"])
            sections_path.write_bytes(sections_bytes)

            cells_path = data_root / "source_table_cells.csv"
            cells_bytes = cells_path.read_bytes()
            cells = _csv_rows(cells_path)
            affix_cell = next(index for index, row in enumerate(cells) if row["source_id"] == "NI-AFFIX-PDF")
            cells.pop(affix_cell)
            _write_csv(cells_path, cells)
            missing_cell = generate(data_root=data_root, pins_path=PINS)
            self.assertEqual(missing_cell["aggregates"]["affix"]["parsed_cells"], 8059)
            self.assertEqual(_entry(missing_cell, "NI-AFFIX-PDF")["status"], "BLOCKED_SOURCE_IDENTITY")
            self.assertNotEqual(missing_cell["receipt_sha256"], baseline["receipt_sha256"])
            cells_path.write_bytes(cells_bytes)

            lexicon_manifest = json.loads(profile_bytes)
            lexicon_manifest["admitted_chapters"].remove("3")
            lexicon_manifest["chapter_receipts"].pop("3")
            for table in ("lexicon_roots", "lexicon_root_senses", "lexicon_root_evidence"):
                path = data_root / f"{table}.csv"
                rows = [row for row in _csv_rows(path) if row["lexicon_chapter"] != "3"]
                _write_csv(path, rows)
                lexicon_manifest["counts"][table] = len(rows)
                lexicon_manifest["output_sha256"][f"{table}.csv"] = hashlib.sha256(path.read_bytes()).hexdigest()
            profile_path.write_bytes(_json_bytes(lexicon_manifest))
            removed = generate(data_root=data_root, pins_path=PINS)
            removed_chapter = _entry(removed, "NI-LEXICON-CURRICULUM", "NI-LEXICON-CURRICULUM:CHAPTER:3")
            self.assertEqual(removed_chapter["status"], "PINNED_UNPARSED")
            self.assertEqual(removed_chapter["canonical_rows"]["lexicon_roots"]["count"], 0)
            self.assertLess(removed["aggregates"]["lexicon"]["roots"], 5810)
            self.assertNotEqual(removed["receipt_sha256"], baseline["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
