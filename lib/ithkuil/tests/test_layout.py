from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = ROOT / "_data" / "csv"
SOURCES = DATA / "sources"


def script_globals(name: str) -> dict:
    return runpy.run_path(str(SRC / name), run_name="ithkuil_layout_contract")


class IthkuilLayoutTests(unittest.TestCase):
    def test_executables_use_canonical_post_move_layout(self):
        fetch = script_globals("fetch_sources.py")
        structure = script_globals("build_structure.py")
        enrichment = script_globals("build_curriculum_enrichment.py")
        morphology = script_globals("build_morphology.py")
        validate = script_globals("validate_dataset.py")

        self.assertEqual(fetch["ROOT"], ROOT)
        self.assertEqual(fetch["RAW"], ROOT / "_raw")
        self.assertEqual(fetch["MANIFEST"], SOURCES / "source_manifest.csv")

        for module in (structure, morphology):
            self.assertEqual(module["ROOT"], ROOT)
            self.assertEqual(module["RAW"], ROOT / "_raw")
            self.assertEqual(module["DATA"], DATA)
            self.assertEqual(module["MANIFEST"], SOURCES / "source_manifest.csv")

        self.assertEqual(enrichment["WORK"], ROOT / "_private" / "curriculum")
        self.assertEqual(enrichment["DATA"], DATA)
        self.assertEqual(enrichment["SOURCES"], SOURCES)
        self.assertEqual(validate["DATA"], DATA)
        self.assertEqual(validate["SOURCES"], SOURCES)

        self.assertTrue((SOURCES / "source_manifest.csv").is_file())
        self.assertTrue((SOURCES / "curriculum_manifest.csv").is_file())
        for legacy in ("data", "sources", "scripts", "_work"):
            self.assertFalse((ROOT / legacy).exists(), legacy)

    def test_documented_commands_and_paths_match_layout(self):
        schema = (ROOT / "SCHEMA.md").read_text(encoding="utf-8")
        readme = (ROOT / "_data" / "README.md").read_text(encoding="utf-8")
        sources = (SOURCES / "README.md").read_text(encoding="utf-8")
        combined = schema + "\n" + readme

        for stale in (
            "python3 scripts/",
            "`data/morphemes_atomic.csv`",
            "`data/morpheme_compositions.csv`",
            "`sources/source_manifest.csv`",
            "`sources/curriculum_manifest.csv`",
            "`_work/curriculum/`",
        ):
            self.assertNotIn(stale, combined)
        self.assertIn("`_private/curriculum/`", combined)
        self.assertIn("`lib/ithkuil/_raw/`", sources)


if __name__ == "__main__":
    unittest.main()
