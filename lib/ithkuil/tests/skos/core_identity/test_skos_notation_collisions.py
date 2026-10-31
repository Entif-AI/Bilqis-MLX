from lib.ithkuil.tests.paths import ITHKUIL_ROOT
import json
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.notation import (
    GRAMMAR_CODE_DATATYPE_IRI,
    NEW_ITHKUIL_DATATYPE_IRI,
    NotationClaim,
    analyze_notation_claims,
    typed_notation,
    validate_notation_collisions,
)


ROOT = ITHKUIL_ROOT
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/skos_notation.json").read_text(encoding="utf-8")
)
DATATYPES = {
    "new-ithkuil": NEW_ITHKUIL_DATATYPE_IRI,
    "grammar-code": GRAMMAR_CODE_DATATYPE_IRI,
}


class NotationCollisionTests(unittest.TestCase):
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

    def test_same_resource_may_carry_multiple_notation_systems(self):
        case = FIXTURE["same_resource_multisystem"]
        resource = URIRef(case["resource_iri"])
        graph = Graph()
        claims = []
        for row in case["notations"]:
            literal = typed_notation(row["lexical"], DATATYPES[row["datatype"]])
            graph.add((resource, SKOS.notation, literal))
            claims.append(
                NotationClaim(
                    FIXTURE["scheme_iri"],
                    case["resource_iri"],
                    literal,
                    expected_unique=True,
                )
            )
        self.assertEqual(len(set(graph.objects(resource, SKOS.notation))), 2)
        self.assertEqual(
            {str(value.datatype) for value in graph.objects(resource, SKOS.notation)},
            {NEW_ITHKUIL_DATATYPE_IRI, GRAMMAR_CODE_DATATYPE_IRI},
        )
        self.assertEqual(analyze_notation_claims(claims).collisions, ())

    def test_collision_report_has_exact_tuple_and_both_resource_iris(self):
        row = FIXTURE["collision"]
        claims = [self.claim(row, iri) for iri in row["resource_iris"]]
        reports = []
        errors = []
        for ordering in (claims, list(reversed(claims))):
            report = analyze_notation_claims(ordering)
            self.assertEqual(len(report.collisions), 1)
            conflict = report.collisions[0]
            self.assertEqual(
                conflict.key.as_tuple(),
                (row["scheme_iri"], DATATYPES[row["datatype"]], row["lexical"]),
            )
            self.assertEqual(conflict.resource_iris, tuple(sorted(row["resource_iris"])))
            reports.append(report.as_dict())

            error = self.assert_code(
                "NOTATION_COLLISION", validate_notation_collisions, ordering
            )
            self.assertIn(f"key={conflict.key.as_tuple()!r}", error.details)
            self.assertIn(f"scheme={row['scheme_iri']}", error.details)
            self.assertIn(
                f"datatype={DATATYPES[row['datatype']]}",
                error.details,
            )
            self.assertIn(f"lexical={row['lexical']!r}", error.details)
            for iri in row["resource_iris"]:
                self.assertIn(f"resource={iri}", error.details)
            errors.append(str(error))

        self.assertEqual(reports[0], reports[1])
        self.assertEqual(errors[0], errors[1])

    def test_non_unique_homograph_is_visible_but_not_rejected(self):
        row = FIXTURE["allowed_homograph"]
        claims = [self.claim(row, iri) for iri in row["resource_iris"]]
        report = validate_notation_collisions(claims)
        self.assertEqual(report.collisions, ())
        self.assertEqual(len(report.allowed_homographs), 1)
        homograph = report.allowed_homographs[0]
        self.assertEqual(
            homograph.key.as_tuple(),
            (row["scheme_iri"], DATATYPES[row["datatype"]], row["lexical"]),
        )
        self.assertEqual(homograph.resource_iris, tuple(sorted(row["resource_iris"])))
        mixed = [
            self.claim(row, row["resource_iris"][0], expected_unique=True),
            self.claim(row, row["resource_iris"][1], expected_unique=False),
        ]
        self.assert_code(
            "NOTATION_COLLISION", validate_notation_collisions, mixed
        )

    def test_duplicate_same_resource_claim_is_idempotent(self):
        row = FIXTURE["collision"]
        claim = self.claim(row, row["resource_iris"][0])
        report = validate_notation_collisions([claim, claim])
        self.assertEqual(report.collisions, ())
        self.assertEqual(report.allowed_homographs, ())

    def test_claim_scheme_and_resource_must_be_absolute_iris(self):
        literal = typed_notation("MFF", GRAMMAR_CODE_DATATYPE_IRI)
        good_scheme = FIXTURE["scheme_iri"]
        good_resource = FIXTURE["collision"]["resource_iris"][0]
        for bad in ("", "relative/path", "/absolute-path-only", "not an IRI"):
            with self.subTest(scheme=bad):
                self.assert_code(
                    "INVALID_NOTATION_SCHEME_IRI",
                    NotationClaim,
                    bad,
                    good_resource,
                    literal,
                )
            with self.subTest(resource=bad):
                self.assert_code(
                    "INVALID_NOTATION_RESOURCE_IRI",
                    NotationClaim,
                    good_scheme,
                    bad,
                    literal,
                )
        for bad in (
            "https://example.test/bad path",
            "https://example.test/<bad>",
            "urn:test:" + chr(0xD800),
        ):
            with self.subTest(scheme=repr(bad)):
                self.assert_code(
                    "INVALID_NOTATION_SCHEME_IRI",
                    NotationClaim,
                    bad,
                    good_resource,
                    literal,
                )
            with self.subTest(resource=repr(bad)):
                self.assert_code(
                    "INVALID_NOTATION_RESOURCE_IRI",
                    NotationClaim,
                    good_scheme,
                    bad,
                    literal,
                )
        self.assertEqual(
            NotationClaim("urn:example:scheme", "urn:example:resource", literal).scheme_iri,
            "urn:example:scheme",
        )

    def test_lexical_match_across_scheme_or_datatype_is_not_a_collision(self):
        lexical = "MFF"
        a = "https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/MFF"
        b = "https://github.com/Entif-AI/Bilqis-MLX/id/grammar/SYNTHETIC/MFF"
        claims = (
            NotationClaim(
                FIXTURE["scheme_iri"],
                a,
                typed_notation(lexical, GRAMMAR_CODE_DATATYPE_IRI),
            ),
            NotationClaim(
                FIXTURE["scheme_iri"],
                b,
                typed_notation(lexical, NEW_ITHKUIL_DATATYPE_IRI),
            ),
            NotationClaim(
                "https://github.com/Entif-AI/Bilqis-MLX/id/scheme/other",
                b,
                typed_notation(lexical, GRAMMAR_CODE_DATATYPE_IRI),
            ),
        )
        self.assertEqual(validate_notation_collisions(claims).collisions, ())


if __name__ == "__main__":
    unittest.main()
