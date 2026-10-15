"""Behavior tests with literal external NI examples from ithkuil.net Chapters 9/13."""
import unittest
from dataclasses import asdict
from bilqis_mlx.ni_construction import (
    Numeral, Referential, ConstructionError,
    generate_numeral, parse_numeral, generate_referential,
    parse_referential, historic_integer_bridge,
)


class NewIthkuilConstructionTests(unittest.TestCase):
    def test_published_number_wordforms_are_literal_external_oracles(self):
        # Grammar 13.4, not generated fixtures. Explicit case is required
        # by this implementation's intentionally narrow subset.
        self.assertEqual(generate_numeral(Numeral(42)).surface, "ksalirsa")
        self.assertEqual(generate_numeral(Numeral(26)).surface, "cpalärsa")
        self.assertEqual(generate_numeral(Numeral(21, shortcut=True)).surface,
                         "wallärsa")
        self.assertEqual(generate_numeral(Numeral(100, case="PAR")).surface,
                         "gzalui")
        self.assertEqual(generate_numeral(Numeral(72)).surface, "ksalorsa")

    def test_independent_parser_decomposes_official_literals(self):
        expected = (
            ("ksalirsa", 42, "THM", False, "i", "ks"),
            ("cpalärsa", 26, "THM", False, "ä", "cp"),
            ("wallärsa", 21, "THM", True, "ä", "ll"),
            ("gzalui", 100, "PAR", False, None, "gz"),
            ("ksalorsa", 72, "THM", False, "o", "ks"),
        )
        for surface, number, case, shortcut, degree, root in expected:
            with self.subTest(surface=surface):
                parsed = parse_numeral(surface)
                self.assertEqual(parsed.semantics["value"], number)
                self.assertEqual(parsed.semantics["case"], case)
                self.assertEqual(parsed.semantics["shortcut"], shortcut)
                self.assertEqual(parsed.slots["III_root"], root)
                self.assertEqual(parsed.slots["IX_case"],
                                 "ui" if case == "PAR" else "a")
                self.assertEqual(parsed.slots["VII_TNX"], (
                    degree + "rs" if degree else "absent"
                ))
                self.assertEqual(parsed.surface, surface)
                self.assertFalse(parsed.model_mastery)

    def test_full_finite_subdomain_roundtrip_and_uniqueness(self):
        surfaces = set()
        for value in range(101):
            for case in ("THM", "PAR"):
                for shortcut in (False, True):
                    output = generate_numeral(Numeral(value, case, shortcut))
                    parsed = parse_numeral(output.surface)
                    self.assertEqual(parsed.semantics,
                                     {"value": value, "case": case,
                                      "shortcut": shortcut,
                                      "meaning": output.semantics["meaning"]})
                    self.assertNotIn(output.surface, surfaces)
                    surfaces.add(output.surface)
        self.assertEqual(len(surfaces), 404)

    def test_minimal_pair_changes_number_not_syntax(self):
        self.assertEqual(parse_numeral("ksalirsa").semantics["value"], 42)
        self.assertEqual(parse_numeral("ksalärsa").semantics["value"], 22)
        self.assertEqual(parse_numeral("ksalorsui").semantics["value"], 72)
        self.assertEqual(parse_numeral("ksalorsui").semantics["case"], "PAR")

    def test_strict_bad_scope_affix_and_case_rejection(self):
        bad = ("ksalrsa", "ksalirsaä", "ksairsa", "ksalrisa",
               "wallärs", "jalar sa", "jxala", "KSALIRSA",
               "jalar sa", "jalar sui", "ksalirs",
               "ksalorsë’i", "ksalirsa gzalui")
        for spelling in bad:
            with self.subTest(spelling=spelling):
                with self.assertRaises(ConstructionError):
                    parse_numeral(spelling)
        with self.assertRaisesRegex(ConstructionError, "OUTSIDE"):
            generate_numeral(Numeral(101))
        with self.assertRaises(ConstructionError):
            generate_numeral(Numeral(True))
        with self.assertRaises(ConstructionError):
            generate_numeral(Numeral(42, case="DAT"))
        with self.assertRaises(ConstructionError):
            generate_numeral(Numeral(42, shortcut="yes"))

    def test_chapter_9_single_neutral_referent_plus_case(self):
        self.assertEqual(generate_referential(Referential("1m", "ERG")).surface,
                         "lo")
        self.assertEqual(generate_referential(Referential("2m", "ABS")).surface,
                         "se")
        self.assertEqual(generate_referential(Referential("mi", "THM")).surface,
                         "za")
        for surface, referent, case in (
            ("lo", "1m", "ERG"),
            ("se", "2m", "ABS"),
            ("za", "mi", "THM"),
            ("mä", "ma", "INS"),
        ):
            analyzed = parse_referential(surface)
            self.assertEqual(analyzed.semantics["referent"], referent)
            self.assertEqual(analyzed.semantics["case"], case)
            self.assertFalse(analyzed.semantics["named_identity"])
        for surface in ("A", "smlo", "lui", "", "loo"):
            with self.assertRaises(ConstructionError):
                parse_referential(surface)
        with self.assertRaises(ConstructionError):
            generate_referential(Referential("A", "THM"))

    def test_no_historic_abi_relabel_or_neural_admission(self):
        bridge = historic_integer_bridge("school.number.42")
        self.assertEqual(bridge["historical_semantics"], "exact integer 42")
        self.assertEqual(bridge["constructed_form"]["surface"], "ksalirsa")
        self.assertEqual(bridge["ni_mapping_kind"],
                         "QUALIFIED_CARDINALITY_NOT_EXACT_SCALAR_EQUIVALENCE")
        self.assertFalse(bridge["legacy_model_token_changed"])
        self.assertFalse(bridge["new_lexical_token_admitted"])
        self.assertEqual(bridge["neural_updates"], 0)
        for value in ("school.number.042", "school.number.-1",
                      "school.number.101", "cogal.value.true"):
            with self.assertRaises(ConstructionError):
                historic_integer_bridge(value)


    def test_all_16_single_neutral_referentials_roundtrip(self):
        for referent in ("1m", "2m", "ma", "mi"):
            for case in ("THM", "ERG", "ABS", "INS"):
                surface = generate_referential(Referential(referent, case)).surface
                parsed = parse_referential(surface)
                self.assertEqual(parsed.semantics["referent"], referent)
                self.assertEqual(parsed.semantics["case"], case)
                self.assertEqual(parsed.slots["C1"] + parsed.slots["VC1"], surface)


if __name__ == "__main__":
    unittest.main()
