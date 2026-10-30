"""A08.1b.4 exact source-notation contrast candidates, not admission."""
from __future__ import annotations

from dataclasses import replace
import os
from unittest import TestCase, skipUnless

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum.scope_source import (
    SourceScopeContrast, check_scope_contrast, source_scope_contrasts,
    source_scope_debt,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection


_ATLAS = os.environ.get("BILQIS_A01_ATLAS_BUNDLE", "")
_SELECTION = AtlasArtifactSelection(
    _ATLAS or "unmounted",
    "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
    "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306",
    "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec",
)


@skipUnless(_ATLAS, "verified A01 bundle not supplied")
class ScopeSourceTests(TestCase):
    def test_unadmitted_source_families_remain_visible(self):
        ledger = source_scope_debt(_SELECTION)
        self.assertEqual(ledger.status, "IMPLEMENTATION_UNCOVERED")
        self.assertEqual(len(ledger.source_held_atomic_rows), 500)
        self.assertEqual(len(ledger.nonconcept_transformations), 19)
        self.assertTrue(all(
            row.owner and row.reason_code
            for row in (*ledger.source_held_atomic_rows,
                        *ledger.nonconcept_transformations)))
        self.assertTrue(any(
            row.key == "ALLO-08d9bb00e7a0dd"
            for row in ledger.nonconcept_transformations))

    def test_real_source_notations_preserve_case_scope_and_illocution(self):
        cases, held = source_scope_contrasts(_SELECTION)
        self.assertEqual(len(cases), 13)
        self.assertEqual(held, ())
        categories = {item.category for item in cases}
        self.assertEqual(categories, {"CASE_SCOPE", "ILLOCUTION"})
        self.assertEqual(len({item.semantic_id for item in cases}), 13)
        for case in cases:
            with self.subTest(semantic_id=case.semantic_id):
                self.assertEqual(case.status,
                                 "SOURCE_NOTATION_NOT_CONTEXTUAL_LAW")
                self.assertTrue(case.source_row.startswith(
                    "atomic/morphemes_atomic/ATOM-"))
                self.assertEqual(case.category,
                                 case.contrast_semantic_id.split("/")[-2])
                self.assertNotEqual(case.grammar_code,
                                    case.contrast_grammar_code)
                self.assertTrue(check_scope_contrast(
                    case, case.semantic_id, _SELECTION))
                self.assertFalse(check_scope_contrast(
                    case, case.contrast_semantic_id, _SELECTION))
                self.assertFalse(check_scope_contrast(
                    case, (case.semantic_id,), _SELECTION))

    def test_self_attested_changed_source_and_answer_spoof_fail(self):
        cases, _ = source_scope_contrasts(_SELECTION)
        case = cases[0]
        for field, forged in (
                ("source_row", "atomic/morphemes_atomic/forged"),
                ("surface_form", "fabricated"),
                ("grammar_code", "CCA.IMAGINARY"),
                ("category", "PHASE"),
                ("source_evidence_sha256", "f" * 64),
                ("semantic_release", "a" * 64),
                ("atlas_bundle_id", "b" * 64),
                ("contrast_semantic_id", "foreign/value"),
                ("status", "ADAPTER_READY")):
            with self.subTest(field=field), self.assertRaises(BilqisError):
                check_scope_contrast(replace(case, **{field: forged}),
                                     case.semantic_id, _SELECTION)

        class Forged(SourceScopeContrast):
            def __eq__(self, other):
                return True

        forged = Forged(**case.__dict__)
        with self.assertRaises(BilqisError):
            check_scope_contrast(forged, case.semantic_id, _SELECTION)

    def test_foreign_atlas_bundle_is_never_a_source_credential(self):
        cases, _ = source_scope_contrasts(_SELECTION)
        with self.assertRaises(BilqisError):
            check_scope_contrast(
                cases[0], cases[0].semantic_id,
                replace(_SELECTION, bundle_id="0" * 64))


if __name__ == "__main__":
    import unittest
    unittest.main()
