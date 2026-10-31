from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
"""Literal affix observations, not inferred morphology."""

import json
import unittest
from pathlib import Path

ROOT = ITHKUIL_ROOT
from lib.ithkuil.src.affix_frontier import extract, output_bytes, parse_table


def ordinary():
    return [["", "-t", "", "DCD* Deictic Demonstratives"]] + [
        [str(n), "", "", f"meaning {n}"] for n in range(1, 10)
    ]


class AffixFrontierTests(unittest.TestCase):
    def test_explicit_degrees_survive_physical_reordering(self):
        matrix = ordinary()
        parsed = parse_table(matrix)
        self.assertEqual((parsed.code, parsed.form), ("DCD", "-t"))
        self.assertEqual(parsed.degrees[1][1], "meaning 1")
        reordered = parse_table([matrix[0], *reversed(matrix[1:])])
        self.assertEqual({n: v[1] for n, v in parsed.degrees.items()},
                         {n: v[1] for n, v in reordered.degrees.items()})

    def test_unknown_shapes_and_duplicate_degrees_fail_closed(self):
        matrix = ordinary()
        self.assertIsNone(parse_table(matrix[1:]))
        self.assertIsNone(parse_table([matrix[0], matrix[1], *matrix[1:9]]))
        matrix[1].append("extra literal")
        self.assertIsNone(parse_table(matrix))
        matrix = ordinary()
        matrix[0][1] = "t"
        self.assertIsNone(parse_table(matrix))

    def test_pin_drift_aborts_before_pdf_open(self):
        with self.assertRaisesRegex(ValueError, "pin mismatch"):
            extract(expected_sha256="0" * 64)

    def test_actual_pdf_source_only_and_repeatable_serialization(self):
        result = extract()
        dcd = next(t for t in result.tables if t["table_id"] == "NI-AFFIX-PDF:AFFIX:DCD")
        self.assertEqual((dcd["source_anchor"], dcd["row_count"]), ("page=3", 10))
        form = next(c for c in result.cells if c["cell_id"] == "NI-AFFIX-PDF:AFFIX:DCD:HEADER:FORM")
        self.assertEqual(form["cell_text"], "-t")
        degrees = [c for c in result.cells if c["table_id"] == dcd["table_id"] and c["cell_id"].endswith(":LABEL")]
        self.assertEqual({c["cell_text"] for c in degrees}, set("123456789"))
        unknown = next(o for o in result.observations if o["kind"] == "table" and o["page"] == 6 and o["table"] == 1)
        self.assertEqual(unknown["disposition"], "UNSUPPORTED")
        repeats = [o for o in result.observations if o.get("code") == "PIC"]
        self.assertTrue(repeats)
        self.assertTrue(all(o["disposition"] == "CONFLICT" for o in repeats))
        self.assertFalse(any("PIC" in t["table_id"] for t in result.tables))
        self.assertEqual(result.receipt["inventory"]["detected_tables"], 440)
        published = json.loads((ROOT / '_data/csv/sources/affix_frontier_manifest.json').read_text())
        self.assertEqual(result.receipt, published['receipt'])
        golden = json.loads((ROOT / 'tests/fixtures/affix_extraction_expected.json').read_text())
        for field, expected in golden.items():
            self.assertEqual(result.receipt[field], expected)
        self.assertEqual(result.receipt['counts'], {'tables': 403, 'cells': 8060, 'observations': 19954})
        meaning = next(c for c in result.cells if c['cell_id'] == 'NI-AFFIX-PDF:AFFIX:DCD:DEGREE:1:MEANING')
        self.assertEqual(meaning['cell_text'],
                         'this X (at/by/near speaker); the X under discussion; the X at hand; '
                         'in this manner/way, in the manner at hand, in said manner')
        self.assertEqual(len(result.tables), 403)
        self.assertEqual(len(result.cells), 8060)
        self.assertEqual(set(output_bytes(result)), {'source_tables.csv', 'source_table_cells.csv'})
        self.assertTrue(all("atomic" not in key for c in result.cells for key in c))


if __name__ == "__main__":
    unittest.main()
