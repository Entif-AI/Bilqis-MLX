from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import csv
import json
from pathlib import Path
from types import MappingProxyType
import unicodedata
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.notation import (
    CANONICAL_NOTATION_DATATYPE_IRIS,
    GRAMMAR_CODE_DATATYPE_IRI,
    NEW_ITHKUIL_DATATYPE_IRI,
    NotationClaim,
    analyze_notation_claims,
    typed_notation,
    validate_notation_collisions,
    validate_notation_literal,
)


ROOT = ITHKUIL_ROOT
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/skos_notation.json").read_text(encoding="utf-8")
)
DATATYPES = MappingProxyType({
    "new-ithkuil": NEW_ITHKUIL_DATATYPE_IRI,
    "grammar-code": GRAMMAR_CODE_DATATYPE_IRI,
})


class NotationContractTests(unittest.TestCase):
    def assert_code(self, code, callable_, *args, **kwargs):
        with self.assertRaises(ProfileError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def claim(self, row, resource_iri, *, expected_unique=None):
        unique = row["expected_unique"] if expected_unique is None else expected_unique
        return NotationClaim(
            row["scheme_iri"],
            resource_iri,
            typed_notation(row["lexical"], DATATYPES[row["datatype"]]),
            expected_unique=unique,
        )

    def test_canonical_datatype_iris_use_the_issue_31_identity_contract(self):
        self.assertEqual(
            NEW_ITHKUIL_DATATYPE_IRI,
            Identity("datatype", ("new-ithkuil",)).iri,
        )
        self.assertEqual(
            GRAMMAR_CODE_DATATYPE_IRI,
            Identity("datatype", ("grammar-code",)).iri,
        )
        self.assertEqual(
            CANONICAL_NOTATION_DATATYPE_IRIS,
            {NEW_ITHKUIL_DATATYPE_IRI, GRAMMAR_CODE_DATATYPE_IRI},
        )

    def test_source_lexical_codepoints_are_preserved_and_language_free(self):
        for row in FIXTURE["roundtrip"]:
            with self.subTest(row=row["id"]):
                literal = typed_notation(row["lexical"], DATATYPES[row["datatype"]])
                self.assertEqual(str(literal), row["lexical"])
                self.assertEqual(
                    tuple(map(ord, str(literal))),
                    tuple(map(ord, row["lexical"])),
                )
                self.assertEqual(str(literal.datatype), DATATYPES[row["datatype"]])
                self.assertIsNone(literal.language)
                self.assertIs(validate_notation_literal(literal), literal)

    def test_source_backed_fixture_values_match_the_relational_ir(self):
        with (ROOT / "_data/csv/morphemes_atomic.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = list(csv.DictReader(handle))
        by_semantic_key = {}
        for row in rows:
            by_semantic_key.setdefault(
                (row["category_code"], row["value_code"]), set()
            ).add(row["surface_form_raw"])

        self.assertIn("ẓ", by_semantic_key[("CONFIGURATION", "MFF")])
        self.assertEqual(by_semantic_key[("CONFIGURATION", "UPX")], {"∅"})
        self.assertIn("i’ö", by_semantic_key[("CASE", "ABL")])

    def test_nfc_and_nfd_lexical_forms_remain_distinct(self):
        by_id = {row["id"]: row for row in FIXTURE["roundtrip"]}
        nfd = by_id["nfd-synthetic-boundary"]["lexical"]
        nfc = by_id["nfc-synthetic-boundary"]["lexical"]
        self.assertNotEqual(nfd, nfc)
        self.assertEqual(unicodedata.normalize("NFC", nfd), nfc)
        self.assertEqual(
            str(typed_notation(nfd, NEW_ITHKUIL_DATATYPE_IRI)),
            nfd,
        )
        self.assertEqual(
            str(typed_notation(nfc, NEW_ITHKUIL_DATATYPE_IRI)),
            nfc,
        )

    def test_zero_empty_and_surrounding_whitespace_policy(self):
        zero = typed_notation("∅", NEW_ITHKUIL_DATATYPE_IRI)
        self.assertEqual(str(zero), "∅")
        self.assert_code(
            "EMPTY_NOTATION", typed_notation, "", NEW_ITHKUIL_DATATYPE_IRI
        )
        for value in (" MFF", "MFF ", "\tMFF", "MFF\n"):
            with self.subTest(value=repr(value)):
                self.assert_code(
                    "NOTATION_SURROUNDING_WHITESPACE",
                    typed_notation,
                    value,
                    GRAMMAR_CODE_DATATYPE_IRI,
                )
        internal = typed_notation("M FF", GRAMMAR_CODE_DATATYPE_IRI)
        self.assertEqual(str(internal), "M FF")

    def test_unpaired_surrogate_code_points_fail_without_repair(self):
        for value in (
            chr(0xD800),
            chr(0xDFFF),
            "x" + chr(0xD800) + "y",
        ):
            with self.subTest(codepoints=tuple(map(ord, value))):
                self.assert_code(
                    "NOTATION_SURROGATE_FORBIDDEN",
                    typed_notation,
                    value,
                    NEW_ITHKUIL_DATATYPE_IRI,
                )
                literal = Literal(
                    value,
                    datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI),
                    normalize=False,
                )
                self.assert_code(
                    "NOTATION_SURROGATE_FORBIDDEN",
                    validate_notation_literal,
                    literal,
                )

    def test_unknown_datatype_and_language_tag_fail_closed(self):
        self.assert_code(
            "UNKNOWN_NOTATION_DATATYPE",
            typed_notation,
            "MFF",
            "https://example.invalid/datatype",
        )
        self.assert_code(
            "NOTATION_LANGUAGE_TAG_FORBIDDEN",
            validate_notation_literal,
            Literal("MFF", lang="en"),
        )
        self.assert_code(
            "NOTATION_LITERAL_REQUIRED",
            validate_notation_literal,
            "MFF",
        )

    def test_true_rdf_parse_serialize_roundtrip_preserves_exact_codepoints(self):
        graph = Graph()
        expected = set()
        for row in FIXTURE["roundtrip"]:
            resource = URIRef(row["resource_iri"])
            literal = typed_notation(row["lexical"], DATATYPES[row["datatype"]])
            graph.add((resource, SKOS.notation, literal))
            expected.add(
                (
                    row["resource_iri"],
                    DATATYPES[row["datatype"]],
                    row["lexical"],
                    tuple(map(ord, row["lexical"])),
                    None,
                )
            )

        serialized = graph.serialize(format="nt")
        parsed = Graph().parse(data=serialized, format="nt")
        observed = {
            (
                str(subject),
                str(obj.datatype),
                str(obj),
                tuple(map(ord, str(obj))),
                obj.language,
            )
            for subject, _, obj in parsed.triples((None, SKOS.notation, None))
        }
        self.assertEqual(observed, expected)

        reparsed = Graph().parse(data=parsed.serialize(format="nt"), format="nt")
        observed_twice = {
            (str(subject), str(obj.datatype), str(obj), tuple(map(ord, str(obj))))
            for subject, _, obj in reparsed.triples((None, SKOS.notation, None))
        }
        self.assertEqual(
            observed_twice,
            {(s, d, lexical, codepoints) for s, d, lexical, codepoints, _ in expected},
        )

if __name__ == "__main__":
    unittest.main()
