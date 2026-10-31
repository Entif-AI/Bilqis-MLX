from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

from lib.ithkuil.tests.source_expectations import CORE
from dataclasses import dataclass, replace
from collections import Counter
import csv
import os
from pathlib import Path
import unittest

from rdflib import Graph, Literal, RDF, URIRef
from rdflib.collection import Collection as RDFCollection
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, RDFS, SKOS

from lib.ithkuil.src.skos.builder import build_core_graph
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.notation import GRAMMAR_CODE_DATATYPE_IRI, NEW_ITHKUIL_DATATYPE_IRI
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.resolver import (
    NEW_ITHKUIL, Realization, RecordRef, ResolvedResource, TextAssertion, resolve_identities,
)
from lib.ithkuil.src.skos.shapes import OrderBasis, OrderedCollectionShape
from lib.ithkuil.src.skos.source import SourceProjector


ROOT = ITHKUIL_ROOT
FIXTURES = FIXTURES
SOURCE_ROOT = Path(os.environ.get("BILQIS_SKOS_SOURCE_ROOT", ROOT / "_data/csv"))
PUBLIC_SOURCE = URIRef("https://www.ithkuil.net/newithkuil_02_morpho-phonology.htm")
SECONDARY = Identity("scheme", ("fixture-secondary",))
ORDER = Identity("ordered_collection", ("fixture-order",))


@dataclass(frozen=True)
class FakeIssue:
    code: str
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeProjection:
    source_graph: Graph
    issues: tuple[FakeIssue, ...] = ()
    held: tuple[RecordRef, ...] = ()


class StubProjector:
    def __init__(self, reject=()):
        self.reject = frozenset(reject)

    def _project(self, identity, refs):
        graph = Graph()
        locus = URIRef(identity.iri.replace("/id/", "/source/locus/") + "-fixture")
        subject = URIRef(identity.iri)
        graph.add((subject, DCTERMS.source, locus))
        graph.add((locus, DCTERMS.source, PUBLIC_SOURCE))
        graph.add((locus, DCTERMS.identifier, Literal("fixture-locus")))
        graph.add((locus, DCTERMS.bibliographicCitation, Literal("Public fixture citation.")))
        graph.add((PUBLIC_SOURCE, DCTERMS.identifier, Literal("NI-WEB-CH02")))
        graph.add((PUBLIC_SOURCE, DCTERMS.bibliographicCitation, Literal("New Ithkuil Chapter 2")))
        if identity.iri in self.reject:
            issue = FakeIssue("SOURCE_URL_NOT_PUBLIC", tuple(refs), ("fixture rejection",))
            return FakeProjection(graph, (issue,), tuple(refs))
        return FakeProjection(graph)

    def project_resource(self, identity, source_records):
        return self._project(identity, source_records)

    def project_group(self, identity, member_source_records):
        return self._project(identity, member_source_records)


def ref(key):
    return RecordRef("morphemes_atomic", key)


def grammar(code, raw, label, *, refs=None, schemes=(NEW_ITHKUIL,), family="fixture-family"):
    refs = tuple(refs or (ref(f"ATOM-{code}"),))
    texts = tuple(
        TextAssertion(source, "surface_form_raw", raw, "source_notation_raw", "realization", None)
        for source in refs
    ) + (TextAssertion(refs[0], "value_name", label, "source_pref_label", "resource", "en"),)
    realizations = tuple(Realization(source, f"normalized-{code}", "fixture", "") for source in refs)
    return ResolvedResource(
        Identity("grammar", ("TEST", code)), "concept", refs, realizations, (family,), texts, schemes,
    )


def root_resource():
    source = RecordRef("lexicon_roots", "ROOT-FIXTURE")
    return ResolvedResource(
        Identity("root", ("NI-WEB-CH02", "ROOT-FIXTURE")), "root", (source,),
        (Realization(source, "č", "source_root_form", ""),), (),
        (
            TextAssertion(source, "root_form_raw", "-Č-", "source_notation_raw", "realization", None),
            TextAssertion(source, "root_gloss", "root fixture", "source_pref_label", "resource", "en"),
        ), (),
    )


def sense_resource():
    source = RecordRef("lexicon_root_senses", "SENSE-FIXTURE")
    return ResolvedResource(
        Identity("sense", ("NI-WEB-CH02", "ROOT-FIXTURE", "STEM 1", "BSC")), "concept",
        (source,), (), (),
        (TextAssertion(source, "sense_summary", "source-defined meaning", "identity_definition",
                       "resource", "en"),), (NEW_ITHKUIL,),
    )


def fixture_resources():
    a_refs = (ref("ATOM-A-1"), ref("ATOM-A-2"))
    a = grammar("A", "∅", "Alpha", refs=a_refs, schemes=(NEW_ITHKUIL, SECONDARY))
    a = replace(a, texts=a.texts + (
        TextAssertion(a_refs[0], "semantic_summary", "realization evidence", "source_note",
                      "realization", "en"),
    ))
    return (a, grammar("B", "ẓ", "Beta"), root_resource(), sense_resource())


def fixture_order(resources):
    members = tuple(r.identity for r in resources if r.identity.kind == "grammar")
    return OrderedCollectionShape(ORDER, members, OrderBasis.SOURCE_SEMANTIC)


class CoreBuilderTests(unittest.TestCase):
    def test_golden_core_graph_covers_all_primitives_and_exact_unicode(self):
        resources = fixture_resources()
        result = build_core_graph(resources, StubProjector(), ordered_collections=(fixture_order(resources),))
        expected = Graph().parse(FIXTURES / "skos_builder_core.ttl", format="turtle")
        self.assertEqual(result.issues, ())
        self.assertTrue(isomorphic(result.graph, expected))
        self.assertEqual(len(result.emitted), 4)
        self.assertEqual(len(resources[0].source_records), 2)
        a = URIRef(resources[0].identity.iri)
        self.assertEqual(list(result.graph.triples((a, RDF.type, SKOS.Concept))),
                         [(a, RDF.type, SKOS.Concept)])
        self.assertEqual(set(result.graph.objects(a, SKOS.inScheme)),
                         {URIRef(NEW_ITHKUIL.iri), URIRef(SECONDARY.iri)})
        self.assertIn(Literal("∅", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI)),
                      set(result.graph.objects(a, SKOS.notation)))
        self.assertIn(Literal("A", datatype=URIRef(GRAMMAR_CODE_DATATYPE_IRI)),
                      set(result.graph.objects(a, SKOS.notation)))
        root = URIRef(root_resource().identity.iri)
        self.assertIn((root, RDF.type, RDFS.Resource), result.graph)
        self.assertIn(Literal("-Č-", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI)),
                      set(result.graph.objects(root, SKOS.notation)))
        self.assertNotIn(Literal("č", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI)),
                         set(result.graph.objects(root, SKOS.notation)))
        core_types = {SKOS.ConceptScheme, SKOS.Concept, SKOS.Collection, SKOS.OrderedCollection,
                      RDFS.Resource}
        core_resources = {subject for subject, _, kind in result.graph.triples((None, RDF.type, None))
                          if kind in core_types}
        self.assertTrue(core_resources)
        self.assertTrue(all(any(result.graph.triples((subject, DCTERMS.source, None)))
                            for subject in core_resources))

    def test_shuffle_is_graph_stable_and_family_membership_never_implies_hierarchy(self):
        resources = fixture_resources()
        shape = fixture_order(resources)
        normal = build_core_graph(resources, StubProjector(), ordered_collections=(shape,))
        shuffled = build_core_graph(reversed(resources), StubProjector(), ordered_collections=(shape,))
        self.assertTrue(isomorphic(normal.graph, shuffled.graph))
        self.assertEqual(set(normal.graph), set(shuffled.graph))
        self.assertEqual(normal.issues, shuffled.issues)
        self.assertEqual(normal.emitted, shuffled.emitted)
        self.assertEqual(list(normal.graph.triples((None, SKOS.broader, None))), [])
        self.assertEqual(list(normal.graph.triples((None, SKOS.narrower, None))), [])
        family = URIRef(Identity("collection", ("fixture-family",)).iri)
        self.assertEqual(len(set(normal.graph.objects(family, SKOS.member))), 2)

    def test_order_requires_explicit_source_semantics_and_closed_member_set(self):
        resources = fixture_resources()
        with self.assertRaises(ProfileError) as caught:
            OrderedCollectionShape(ORDER, fixture_order(resources).members, OrderBasis.CURRICULUM)
        self.assertEqual(caught.exception.code, "ORDER_BASIS_NOT_SOURCE_SEMANTIC")
        without_manifest = build_core_graph(resources, StubProjector())
        self.assertEqual(list(without_manifest.graph.triples((None, SKOS.memberList, None))), [])
        held = replace(resources[1], texts=resources[1].texts + (
            TextAssertion(resources[1].source_records[0], "value_name", "conflict",
                          "source_pref_label", "resource", "en"),
        ))
        result = build_core_graph((resources[0], held, resources[2], resources[3]), StubProjector(),
                                  ordered_collections=(fixture_order(resources),))
        self.assertFalse(any(result.graph.triples((URIRef(ORDER.iri), SKOS.memberList, None))))
        self.assertIn("ORDERED_COLLECTION_MEMBER_NOT_EMITTED",
                      {issue.code for issue in result.issues if issue.resource_iri == ORDER.iri})

    def test_text_source_and_shape_failures_hold_entire_resource(self):
        base = fixture_resources()[0]
        conflicting = replace(base, texts=base.texts + (
            TextAssertion(base.source_records[0], "value_name", "Different", "source_pref_label",
                          "resource", "en"),
        ))
        ghost = TextAssertion(ref("GHOST"), "value_name", "Ghost", "source_pref_label", "resource", "en")
        wrong_ref = replace(base, texts=base.texts + (ghost,))
        wrong_shape = replace(root_resource(), role="concept", schemes=(NEW_ITHKUIL,))
        cases = ((conflicting, StubProjector(), "PREFERRED_LABEL_CONFLICT"),
                 (wrong_ref, StubProjector(), "TEXT_SOURCE_REF_NOT_RESOURCE"),
                 (wrong_shape, StubProjector(), "INVALID_CONCEPT_IDENTITY"),
                 (base, StubProjector((base.identity.iri,)), "SOURCE_URL_NOT_PUBLIC"))
        for resource, projector, code in cases:
            with self.subTest(code=code):
                result = build_core_graph((resource,), projector)
                self.assertEqual(result.emitted, ())
                self.assertIn(code, {issue.code for issue in result.issues})
                iri = URIRef(resource.identity.iri)
                self.assertFalse(any(result.graph.triples((iri, None, None))))
                self.assertFalse(any(result.graph.triples((None, None, iri))))

    def test_collision_holds_every_claimant_and_scheme_failure_blocks_concepts(self):
        a = grammar("A", "same-raw", "Alpha")
        b = grammar("B", "same-raw", "Beta")
        collision = build_core_graph((a, b), StubProjector())
        self.assertEqual(collision.emitted, ())
        self.assertEqual({issue.resource_iri for issue in collision.issues
                          if issue.code == "NOTATION_COLLISION"}, {a.identity.iri, b.identity.iri})
        scheme_failure = build_core_graph((a, root_resource()), StubProjector((NEW_ITHKUIL.iri,)))
        self.assertEqual(tuple(r.identity.kind for r in scheme_failure.emitted), ("root",))
        self.assertIn("SCHEME_SOURCE_BLOCKED", {issue.code for issue in scheme_failure.issues})
        self.assertNotIn((URIRef(NEW_ITHKUIL.iri), RDF.type, SKOS.ConceptScheme), scheme_failure.graph)

    def test_current_corpus_accounting_and_level_order_are_fail_closed(self):
        closure = preflight(SOURCE_ROOT).require_valid()
        resolution = resolve_identities(closure)
        projector = SourceProjector(closure)
        baseline = build_core_graph(resolution.resources, projector)
        self.assertEqual((len(resolution.resources), len(resolution.issues)), (CORE["resolved_resources"], 0))
        self.assertEqual((len(baseline.emitted), len(baseline.issues)), (CORE["emitted_resources"], 568))
        self.assertEqual(Counter(issue.code for issue in baseline.issues),
                         Counter({"NOTATION_COLLISION": 567, "SOURCE_TEXT_TOO_LONG": 1}))
        self.assertEqual(len({r.identity.iri for r in resolution.resources} -
                             {r.identity.iri for r in baseline.emitted}), 389)
        held = {r.identity.iri for r in resolution.resources} - {r.identity.iri for r in baseline.emitted}
        self.assertFalse(any(any(baseline.graph.triples((URIRef(iri), None, None))) for iri in held))
        self.assertFalse(any(any(baseline.graph.triples((None, None, URIRef(iri)))) for iri in held))
        levels = tuple(Identity("grammar", ("LEVEL", code)) for code in
                       ("MIN", "SBE", "IFR", "DFT", "EQU", "SUR", "SPL", "SPQ", "MAX"))
        shape = OrderedCollectionShape(Identity("ordered_collection", ("level-scale",)), levels,
                                       OrderBasis.SOURCE_SEMANTIC)
        result = build_core_graph(resolution.resources, projector, ordered_collections=(shape,))
        self.assertFalse(any(result.graph.triples((URIRef(shape.identity.iri), SKOS.memberList, None))))
        issue = next(i for i in result.issues if i.resource_iri == shape.identity.iri)
        self.assertEqual(issue.code, "ORDERED_COLLECTION_MEMBER_NOT_EMITTED")
        self.assertEqual({detail.removeprefix("member=") for detail in issue.details},
                         {member.iri for member in levels})

    def test_source_qualified_level_slice_emits_complete_original_order(self):
        closure = preflight(SOURCE_ROOT).require_valid()
        resolution = resolve_identities(closure)
        codes = ("MIN", "SBE", "IFR", "DFT", "EQU", "SUR", "SPL", "SPQ", "MAX")
        identities = tuple(Identity("grammar", ("LEVEL", code)) for code in codes)
        resources = tuple(resource for resource in resolution.resources if resource.identity in identities)
        self.assertEqual(len(resources), 9)
        # The overview is the atoms' primary locus; this detailed source table
        # separately attests the semantic Level order, not the CSV iteration.
        with (SOURCE_ROOT / "source_table_cells.csv").open(newline="", encoding="utf-8") as handle:
            source_cells = {(int(row["row_index"]), int(row["column_index"])): row["cell_text"]
                            for row in csv.DictReader(handle) if row["table_id"] == "NI-WEB-CH05:T034"}
        self.assertEqual(tuple(source_cells[(row, 1)] for row in range(2, 11)), codes)
        shape = OrderedCollectionShape(Identity("ordered_collection", ("level-scale",)), identities,
                                       OrderBasis.SOURCE_SEMANTIC)
        result = build_core_graph(resources, SourceProjector(closure), ordered_collections=(shape,))
        self.assertEqual(result.issues, ())
        head = result.graph.value(URIRef(shape.identity.iri), SKOS.memberList)
        self.assertEqual(tuple(RDFCollection(result.graph, head)), tuple(URIRef(identity.iri) for identity in identities))
        self.assertEqual(set(result.graph.subjects(RDF.type, SKOS.Concept)),
                         {URIRef(identity.iri) for identity in identities})

    def test_conflicting_order_manifests_have_input_order_independent_held_reason(self):
        resources = fixture_resources()
        first = fixture_order(resources)
        second = replace(first, members=tuple(reversed(first.members)))
        normal = build_core_graph(resources, StubProjector(), ordered_collections=(first, second))
        reverse = build_core_graph(resources, StubProjector(), ordered_collections=(second, first))
        self.assertEqual(normal.issues, reverse.issues)
        self.assertTrue(isomorphic(normal.graph, reverse.graph))
        self.assertEqual([issue.code for issue in normal.issues], ["ORDERED_COLLECTION_REDEFINED"])
        self.assertFalse(any(normal.graph.triples((URIRef(first.identity.iri), SKOS.memberList, None))))


if __name__ == "__main__":
    unittest.main()
