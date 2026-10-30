"""A08.1b.3: source-law evidence is not a constructive lesson grant."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import morphology_source as source
from bilqis_mlx.semantics.atlas_projection import (
    FormalDomainBinding, compile_atlas_release, persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection


COMPOSITION_ID = "COMP-1a7a421841756f"
HELD_COMPOSITION_ID = "COMP-00a9e6c3998d74"


class MorphologySourceTests(unittest.TestCase):
    def test_law_record_cannot_claim_factory_admission(self):
        valid = source.MorphologySourceLaw(
            "a" * 64, "b" * 64, COMPOSITION_ID,
            ("atom:ea", "atom:bz"), ("ea", "bẓ"), "eabẓ",
            "NI-WEB-CH05", "NI-WEB-CH05:T023", "8968",
            "#61", ("source=NI-WEB-CH05;table=NI-WEB-CH05:T023;line=8968",),
            "c" * 64, "d" * 64, "e" * 64, "1" * 64, "f" * 64)
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
        root = Path(__file__).resolve().parents[4]
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
                "ATOM-48da4ee9e28239", "ATOM-c413d0e6c8faa8"))
            self.assertEqual(law.component_forms, ("ea", "bẓ"))
            self.assertEqual(law.surface_form, "eabẓ")
            self.assertEqual(law.source_table_id, "NI-WEB-CH05:T023")
            self.assertEqual(law.source_owner, "#61")
            self.assertEqual(len(law.source_loci), 2)
            self.assertTrue(any("table=NI-WEB-CH05:T023" in item
                                for item in law.source_loci))
            self.assertTrue(any("table=NI-WEB-CH07:T003" in item
                                for item in law.source_loci))
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
                    selection, corpus, HELD_COMPOSITION_ID)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
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
