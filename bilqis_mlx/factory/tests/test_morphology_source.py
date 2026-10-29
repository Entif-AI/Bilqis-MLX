"""A08.1b.3: source-law evidence is not a constructive lesson grant."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import morphology_source as source
from bilqis_mlx.semantics.atlas_projection import (
    FormalDomainBinding, compile_atlas_release, persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection


COMPOSITION_ID = "COMP-00a9e6c3998d74"


class MorphologySourceTests(unittest.TestCase):
    def test_frontier_and_source_tables_are_exact_byte_pinned(self):
        tables = source._source_tables(source._CSV_ROOT)
        self.assertTrue(any(
            item["composition_id"] == COMPOSITION_ID
            for item in tables["morpheme_compositions.csv"]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sources").mkdir()
            shutil.copy2(
                source._CSV_ROOT / "sources/extraction_frontier.json",
                root / "sources/extraction_frontier.json")
            for name, _ in source._TABLES:
                shutil.copy2(source._CSV_ROOT / name, root / name)
            with (root / "morpheme_compositions.csv").open("ab") as file:
                file.write(b"\nforged,source,row\n")
            with self.assertRaises(BilqisError) as caught:
                source._source_tables(root)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_MORPHOLOGY_SOURCE_TABLE_DRIFT")
            receipt_path = root / "sources/extraction_frontier.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["schema"] = "forged/v9"
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaises(BilqisError):
                source._frontier_receipt(root)

    def test_law_record_cannot_claim_factory_admission(self):
        valid = source.MorphologySourceLaw(
            "a" * 64, "b" * 64, COMPOSITION_ID,
            ("atom:a", "atom:sw"), ("a", "sw"), "asw",
            "NI-WEB-CH07", "NI-WEB-CH07:T011", "5709",
            "c" * 64, "d" * 64, "e" * 64, "f" * 64)
        self.assertEqual(valid.status, "SOURCE_ROW_EVIDENCE_NOT_ADMITTED")
        for change in (
                {"status": "ADAPTER_READY"},
                {"schema": "forged/v9"},
                {"surface_form": "fake"},
                {"component_forms": ("a", "zz")}):
            with self.subTest(change=change):
                with self.assertRaises(BilqisError):
                    replace(valid, **change)

    def test_real_a01_source_row_and_exact_component_law_if_supplied(self):
        corpus = os.environ.get("BILQIS_ATLAS_REAL_CORPUS")
        if not corpus:
            self.skipTest("real pinned A01 corpus not supplied")
        root = Path(__file__).resolve().parents[3]
        prior = root / "bilqis_mlx/semantics/copular_registry_v1.json"
        boolean = root / "bilqis_mlx/semantics/legacy_abi_v1.json"
        numeric = root / "bilqis_mlx/semantics/numeric_v1.json"
        bindings = (
            FormalDomainBinding(
                "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json",
                hashlib.sha256(boolean.read_bytes()).hexdigest(),
                ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
                ("B.NOT", "B.AND")),
            FormalDomainBinding(
                "numeric", "bilqis_mlx/semantics/numeric_v1.json",
                hashlib.sha256(numeric.read_bytes()).hexdigest(),
                ("bilqis.numeric/v1:school.op.COUNT",
                 "bilqis.numeric/v1:school.op.SUCC"),
                ("C.COUNT", "C.SUCCESSOR")))
        release = compile_atlas_release(
            corpus, Path(corpus) / "coverage.json", prior, bindings)
        with tempfile.TemporaryDirectory() as directory:
            artifact = persist_atlas_release(release, directory)
            selection = AtlasArtifactSelection(
                artifact.path, artifact.bundle_id, release.digest,
                release.source_bundle_id)
            law = source.resolve_morphology_source_law(
                selection, corpus, COMPOSITION_ID)
            self.assertEqual(law.component_ids, (
                "ATOM-b062726ad5143d", "ATOM-7671e7f56ccfb8"))
            self.assertEqual(law.component_forms, ("a", "sw"))
            self.assertEqual(law.surface_form, "asw")
            self.assertEqual(law.source_table_id, "NI-WEB-CH07:T011")
            self.assertEqual(law.status, "SOURCE_ROW_EVIDENCE_NOT_ADMITTED")
            source.assert_morphology_source_law_current(
                law, selection, corpus)
            object.__setattr__(law, "source_table_id", "NI-WEB-CH07:T012")
            with self.assertRaises(BilqisError) as caught:
                source.assert_morphology_source_law_current(
                    law, selection, corpus)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_MORPHOLOGY_LAW_SOURCE_DRIFT")
            with self.assertRaises(BilqisError) as caught:
                source.resolve_morphology_source_law(
                    selection, corpus, "COMP-0060583f4d9807")
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
            with self.assertRaises(BilqisError) as caught:
                source.resolve_morphology_source_law(
                    selection, corpus, "COMP-not-in-A01")
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_MORPHOLOGY_SOURCE_ROW_UNPINNED")


if __name__ == "__main__":
    unittest.main()
