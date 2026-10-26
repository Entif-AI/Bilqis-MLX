import csv
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from rdflib import Graph, URIRef
from rdflib.collection import Collection as RDFCollection
from rdflib.compare import isomorphic
from rdflib.namespace import RDF, RDFS, SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.shapes import (
    CollectionShape,
    ConceptShape,
    OrderBasis,
    OrderedCollectionShape,
    RootResourceShape,
    SchemeShape,
    build_shape_graph,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


def grammar(category: str, value: str) -> Identity:
    return Identity("grammar", (category, value))


NEW_ITHKUIL = Identity("scheme", ("new-ithkuil",))
SHARED_FIXTURE = Identity("scheme", ("shared-shape-fixture",))
MFF = grammar("CONFIGURATION", "MFF")
UPX = grammar("CONFIGURATION", "UPX")
ACT = grammar("CASE", "ACT")
INS = grammar("CASE", "INS")
NRR = grammar("REGISTER", "NRR")
DSV = grammar("REGISTER", "DSV")
LEVELS = tuple(grammar("LEVEL", code) for code in (
    "MIN", "SBE", "IFR", "DFT", "EQU", "SUR", "SPL", "SPQ", "MAX",
))
ROOT_ID = Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e"))
SENSE_1 = Identity(
    "sense", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e", "STEM 1", "BSC")
)
SENSE_2 = Identity(
    "sense", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e", "STEM 2", "BSC")
)


def fixture_shapes():
    concepts = (
        ConceptShape(MFF, (NEW_ITHKUIL, SHARED_FIXTURE)),
        ConceptShape(UPX, (NEW_ITHKUIL,)),
        ConceptShape(ACT, (NEW_ITHKUIL,)),
        ConceptShape(INS, (NEW_ITHKUIL,)),
        ConceptShape(NRR, (NEW_ITHKUIL,)),
        ConceptShape(DSV, (NEW_ITHKUIL,)),
        *(ConceptShape(level, (NEW_ITHKUIL,)) for level in LEVELS),
        ConceptShape(SENSE_1, (NEW_ITHKUIL,)),
        ConceptShape(SENSE_2, (NEW_ITHKUIL,)),
    )
    return (
        SchemeShape(NEW_ITHKUIL),
        SchemeShape(SHARED_FIXTURE),
        *concepts,
        CollectionShape(Identity("collection", ("configuration",)), (MFF, UPX)),
        CollectionShape(Identity("collection", ("case",)), (ACT, INS)),
        CollectionShape(Identity("collection", ("register",)), (NRR, DSV)),
        OrderedCollectionShape(
            Identity("ordered_collection", ("level-scale",)),
            LEVELS,
            OrderBasis.SOURCE_SEMANTIC,
        ),
        RootResourceShape(ROOT_ID),
    )


class ShapeContractTests(unittest.TestCase):
    def assert_code(self, code, callable_, *args, **kwargs):
        with self.assertRaises(ProfileError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_positive_rdf_fixture_matches_exact_resource_shapes(self):
        actual = build_shape_graph(fixture_shapes())
        expected = Graph().parse(FIXTURES / "skos_shapes_positive.ttl", format="turtle")
        self.assertTrue(isomorphic(actual, expected))

    def test_shape_specs_are_frozen_and_graph_build_is_repeatable(self):
        concept = ConceptShape(MFF, (NEW_ITHKUIL, SHARED_FIXTURE))
        with self.assertRaises(FrozenInstanceError):
            concept.schemes = (NEW_ITHKUIL,)
        self.assertTrue(isomorphic(
            build_shape_graph(fixture_shapes()),
            build_shape_graph(fixture_shapes()),
        ))

    def test_multischeme_participation_keeps_one_concept_identity(self):
        graph = build_shape_graph(fixture_shapes())
        subject = URIRef(MFF.iri)
        self.assertEqual(set(graph.objects(subject, SKOS.inScheme)), {
            URIRef(NEW_ITHKUIL.iri), URIRef(SHARED_FIXTURE.iri),
        })
        self.assertEqual(list(graph.triples((subject, RDF.type, SKOS.Concept))), [
            (subject, RDF.type, SKOS.Concept)
        ])

    def test_configuration_case_and_register_are_unordered_collections(self):
        graph = build_shape_graph(fixture_shapes())
        expected = {
            "configuration": {MFF, UPX},
            "case": {ACT, INS},
            "register": {NRR, DSV},
        }
        for family, members in expected.items():
            collection = URIRef(Identity("collection", (family,)).iri)
            self.assertIn((collection, RDF.type, SKOS.Collection), graph)
            self.assertNotIn((collection, RDF.type, SKOS.OrderedCollection), graph)
            self.assertEqual(set(graph.objects(collection, SKOS.member)), {
                URIRef(member.iri) for member in members
            })

    def test_family_membership_emits_no_false_hierarchy(self):
        graph = build_shape_graph(fixture_shapes())
        self.assertEqual(list(graph.triples((None, SKOS.broader, None))), [])
        self.assertEqual(list(graph.triples((None, SKOS.narrower, None))), [])
        forbidden = Graph().parse(FIXTURES / "skos_shapes_forbidden.ttl", format="turtle")
        self.assertEqual(set(graph) & set(forbidden), set())

    def test_only_source_semantic_order_can_create_ordered_collection(self):
        for basis in (
            OrderBasis.CSV_ROW,
            OrderBasis.SOURCE_TABLE,
            OrderBasis.SOURCE_CHAPTER,
            OrderBasis.CURRICULUM,
        ):
            self.assert_code(
                "ORDER_BASIS_NOT_SOURCE_SEMANTIC",
                OrderedCollectionShape,
                Identity("ordered_collection", ("forbidden-order",)),
                LEVELS,
                basis,
            )

        graph = build_shape_graph(fixture_shapes())
        ordered = URIRef(Identity("ordered_collection", ("level-scale",)).iri)
        heads = list(graph.objects(ordered, SKOS.memberList))
        self.assertEqual(len(heads), 1)
        self.assertEqual(list(RDFCollection(graph, heads[0])), [URIRef(level.iri) for level in LEVELS])

    def test_level_order_fixture_is_bound_to_source_semantics(self):
        with (ROOT / "_data/csv/source_table_cells.csv").open(newline="", encoding="utf-8") as handle:
            rows = [
                row for row in csv.DictReader(handle)
                if row["table_id"] == "NI-WEB-CH05:T034" and int(row["row_index"]) >= 2
            ]
        values = {
            (int(row["row_index"]), int(row["column_index"])): row["cell_text"]
            for row in rows
        }
        self.assertEqual(
            tuple(values[(row, 1)] for row in range(2, 11)),
            tuple(level.keys[1] for level in LEVELS),
        )
        self.assertEqual(
            tuple(values[(row, 2)] for row in range(2, 11)),
            (
                "MINIMAL", "SUBEQUATIVE", "INFERIOR", "DEFICIENT", "EQUATIVE",
                "SURPASSIVE", "SUPERLATIVE", "SUPEREQUATIVE", "MAXIMAL",
            ),
        )

    def test_shuffled_unordered_source_rows_do_not_create_order(self):
        normal = build_shape_graph(fixture_shapes())
        altered = []
        for resource in reversed(fixture_shapes()):
            if isinstance(resource, CollectionShape):
                resource = CollectionShape(resource.identity, tuple(reversed(resource.members)))
            altered.append(resource)
        shuffled = build_shape_graph(altered)
        self.assertTrue(isomorphic(normal, shuffled))

    def test_root_resource_stays_distinct_from_its_sense_concepts(self):
        graph = build_shape_graph(fixture_shapes())
        root = URIRef(ROOT_ID.iri)
        self.assertIn((root, RDF.type, RDFS.Resource), graph)
        self.assertNotIn((root, RDF.type, SKOS.Concept), graph)
        self.assertEqual(list(graph.objects(root, SKOS.inScheme)), [])
        for sense in (SENSE_1, SENSE_2):
            subject = URIRef(sense.iri)
            self.assertNotEqual(subject, root)
            self.assertIn((subject, RDF.type, SKOS.Concept), graph)
            self.assertIn((subject, SKOS.inScheme, URIRef(NEW_ITHKUIL.iri)), graph)

    def test_shape_references_fail_closed(self):
        undeclared = Identity("scheme", ("undeclared",))
        self.assert_code(
            "UNDECLARED_CONCEPT_SCHEME",
            build_shape_graph,
            (ConceptShape(MFF, (undeclared,)),),
        )
        self.assert_code(
            "UNDECLARED_COLLECTION_MEMBER",
            build_shape_graph,
            (
                SchemeShape(NEW_ITHKUIL),
                CollectionShape(Identity("collection", ("configuration",)), (MFF,)),
            ),
        )
        self.assert_code(
            "INVALID_CONCEPT_IDENTITY",
            ConceptShape,
            ROOT_ID,
            (NEW_ITHKUIL,),
        )
        self.assert_code(
            "INVALID_SCHEME_IDENTITY",
            SchemeShape,
            ROOT_ID,
        )

    def test_mutable_members_cannot_change_frozen_shape_after_validation(self):
        self.assert_code("SHAPE_MEMBERS_MUST_BE_IMMUTABLE", ConceptShape, MFF, [NEW_ITHKUIL])
        self.assert_code("SHAPE_MEMBERS_MUST_BE_IMMUTABLE", CollectionShape,
                         Identity("collection", ("configuration",)), [MFF, UPX])

    def test_unknown_shapes_and_invalid_identity_objects_fail_closed(self):
        self.assert_code("UNKNOWN_RESOURCE_SHAPE", build_shape_graph, [object()])
        self.assert_code("INVALID_SCHEME_IDENTITY", SchemeShape, "new-ithkuil")


if __name__ == "__main__":
    unittest.main()
