"""Source-backed golden Configuration projection for issue #44."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, RDF, SKOS

from lib.ithkuil.src.skos.builder import build_core_graph
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.configuration import select_configuration_resources
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.notation import (
    GRAMMAR_CODE_DATATYPE_IRI,
    NEW_ITHKUIL_DATATYPE_IRI,
)
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.resolver import resolve_identities
from lib.ithkuil.src.skos.source import SourceProjector


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCHEME = "https://github.com/Entif-AI/Bilqis-MLX/id/scheme/new-ithkuil"
COLLECTION = "https://github.com/Entif-AI/Bilqis-MLX/id/collection/configuration"
LOCUS = "https://github.com/Entif-AI/Bilqis-MLX/source/locus/9f390b250fdced5e651cb9c136d2b4c1b20947f3cb5b6ce15c70f2e549b4dfba"
SOURCE_URL = "https://www.ithkuil.net/newithkuil_03_morphology.htm"
CANONICAL_SHA256 = "a415febbec9e0b53a6cd251d99853b8c23ac53a0e17af986a1e19a1178ae5b42"

EXPECTED = (
    ("DDC", "duplex/dissimilar/connected", "fs", "overt", "ATOM-dc946979ae94bc", "AST-3d56c18f5c8a1a"),
    ("DDF", "duplex/dissimilar/fused", "š", "overt", "ATOM-84b18ab270f037", "AST-0e1db9d1b02687"),
    ("DDS", "duplex/dissimilar/separate", "ţs", "overt", "ATOM-02a4496bfbac3a", "AST-54b66e2ec43212"),
    ("DFC", "duplex/fuzzy/connected", "kš", "overt", "ATOM-1ed3c4cb9bda54", "AST-58900ebc63821e"),
    ("DFF", "duplex/fuzzy/fused", "pš", "overt", "ATOM-f7597840097422", "AST-a1dad67913de1c"),
    ("DFS", "duplex/fuzzy/separate", "č", "overt", "ATOM-9dfb6843452719", "AST-42c2a98c4d34dd"),
    ("DPX", "duplex", "s", "overt", "ATOM-8737658f2e4fa3", "AST-65a9aba2aa4f9a"),
    ("DSC", "duplex/similar/connected", "ks", "overt", "ATOM-c22f906a7c2334", "AST-cbb9ab44a8e23c"),
    ("DSF", "duplex/similar/fused", "ps", "overt", "ATOM-446b5a7f8edb52", "AST-4a7a9d3ae1825b"),
    ("DSS", "duplex/similar/separate", "c", "overt", "ATOM-a2a407c1a80a7f", "AST-f3d0208c98f9d6"),
    ("MDC", "multiplex/dissimilar/connected", "f", "overt", "ATOM-889fbd2e2d448d", "AST-4c42a42b822f8e"),
    ("MDF", "multiplex/dissimilar/fused", "ç", "overt", "ATOM-f30d2dac460dee", "AST-5e0696176dacb5"),
    ("MDS", "multiplex/dissimilar/separate", "ţ", "overt", "ATOM-b1859b8dc8015f", "AST-f08be0ab79c7d4"),
    ("MFC", "multiplex/fuzzy/connected", "ž", "overt", "ATOM-4194a9ce6ef684", "AST-1e027036693dfd"),
    ("MFF", "multiplex/fuzzy/fused", "ẓ", "overt", "ATOM-5ea26e72589ea3", "AST-5faad30f6ed114"),
    ("MFS", "multiplex/fuzzy/separate", "z", "overt", "ATOM-b894d2fdeb8eac", "AST-1a01794fe7ed57"),
    ("MSC", "multiplex/similar/connected", "k", "overt", "ATOM-ca21e9b2c27d6a", "AST-8045a9edb54181"),
    ("MSF", "multiplex/similar/fused", "p", "overt", "ATOM-94fa4f3bab535c", "AST-5e8225749361a4"),
    ("MSS", "multiplex/similar/separate", "t", "overt", "ATOM-141cf12b11fa90", "AST-5ee3857ebef85d"),
    ("UPX", "uniplex", "∅", "zero", "ATOM-e09a479fdaca6d", "AST-6235ff207f4367"),
)

FILE_DIGESTS = {
    "morphemes_atomic.csv": "6c6e2ea64a659b7061bdc3d388201c6219207bc1aa002869537f56d1f7ddf083",
    "source_assertions.csv": "20a197bd4ca9757c19b731652d124139109351294a3b561fb456c81f2e922f7d",
    "source_sections.csv": "765f30d97c64b68266a45cf77fed69cdba2ce70d5ec368ec1d6c817c259d856f",
    "source_tables.csv": "ef0ebb70ad5373c7e75cf318377aee44723fa676eda5d4366ce236a6ffa79b65",
    "sources/source_manifest.csv": "3e151b90b7140db9ee1319d4c16b2da3d8bd3aa675da5e0a9e20e57ce61b4b83",
}


class ConfigurationGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.resolution = resolve_identities(cls.closure)
        cls.selection = select_configuration_resources(cls.closure, cls.resolution)
        cls.build = build_core_graph(cls.selection.resources, SourceProjector(cls.closure))
        cls.canonical = canonicalize(cls.build.graph)
        cls.source_fixture = json.loads((FIXTURES / "configuration_source.json").read_text(encoding="utf-8"))

    def test_literal_source_fixture_matches_tracked_snapshot(self) -> None:
        for relative, digest in FILE_DIGESTS.items():
            self.assertEqual(hashlib.sha256((SOURCE_ROOT / relative).read_bytes()).hexdigest(), digest)
        self.assertEqual(self.source_fixture["tracked_input_digests"], FILE_DIGESTS)
        self.assertEqual(
            self.source_fixture["source_document"],
            {
                "content_type": "text/html",
                "final_url": SOURCE_URL,
                "sha256": "93d9d61682fa2d051fc667cf2952a0e521b07ec42629e2788f57b0b2f4c34c0f",
                "source_id": "NI-WEB-CH03",
                "source_type": "grammar_chapter",
                "title": "Chapter 3: Morphology",
            },
        )
        self.assertEqual(
            self.source_fixture["source_section"],
            {
                "section_id": "NI-WEB-CH03:3.1",
                "section_number": "3.1",
                "section_title": "Configuration",
                "source_heading_text": "Configuration",
                "source_id": "NI-WEB-CH03",
                "source_line": "3063",
                "source_url": SOURCE_URL,
            },
        )
        self.assertEqual(
            self.source_fixture["source_table"],
            {
                "column_count": "7",
                "row_count": "10",
                "section_id": "NI-WEB-CH03:3.1",
                "source_id": "NI-WEB-CH03",
                "source_line": "3239",
                "source_url": SOURCE_URL,
                "table_id": "NI-WEB-CH03:T003",
                "table_role": "structured_table",
            },
        )
        self.assertEqual(self.source_fixture["expected_scheme_iri"], SCHEME)
        self.assertEqual(self.source_fixture["expected_collection_iri"], COLLECTION)
        self.assertEqual(self.source_fixture["expected_source_locus_iri"], LOCUS)
        self.assertEqual(
            self.source_fixture["expected_new_ithkuil_datatype_iri"],
            NEW_ITHKUIL_DATATYPE_IRI,
        )
        self.assertEqual(
            self.source_fixture["expected_grammar_code_datatype_iri"],
            GRAMMAR_CODE_DATATYPE_IRI,
        )
        rows = {row["atomic_id"]: row for row in self.closure.table("morphemes_atomic").rows}
        assertions = {
            row["entity_id"]: row
            for row in self.closure.table("source_assertions").rows
            if row["entity_kind"] == "atomic_morpheme"
        }
        literal = tuple(
            (
                row["value_code"], row["value_name"], row["surface_form_raw"],
                row["realization_type"], row["atomic_id"], assertions[row["atomic_id"]]["assertion_id"],
            )
            for row in sorted(
                (item for item in rows.values() if item["category_code"] == "CONFIGURATION"),
                key=lambda item: item["value_code"],
            )
        )
        self.assertEqual(literal, EXPECTED)
        for row in (item for item in rows.values() if item["category_code"] == "CONFIGURATION"):
            self.assertEqual(
                (
                    row["category_name"], row["morpheme_family"], row["morpheme_class"],
                    row["primary_source_id"], row["primary_section_id"],
                    row["primary_table_id"], row["primary_source_line"],
                    row["primary_source_url"], row["evidence_status"],
                ),
                (
                    "Configuration", "configuration", "CA_consonantal_exponent",
                    "NI-WEB-CH03", "NI-WEB-CH03:3.1", "NI-WEB-CH03:T003", "3239",
                    SOURCE_URL, "official_source_observed",
                ),
            )
            assertion = assertions[row["atomic_id"]]
            self.assertEqual(
                (
                    assertion["assertion_kind"], assertion["source_id"], assertion["section_id"],
                    assertion["table_id"], assertion["source_line"], assertion["source_url"],
                    assertion["evidence_status"],
                ),
                (
                    "form_value", "NI-WEB-CH03", "NI-WEB-CH03:3.1", "NI-WEB-CH03:T003",
                    "3239", SOURCE_URL, "official_source_observed",
                ),
            )
        fixture_literal = tuple(
            (
                item["value_code"], item["value_name"], item["surface_form_raw"],
                item["realization_type"], item["atomic_id"], item["source_assertion_id"],
            )
            for item in self.source_fixture["records"]
        )
        self.assertEqual(fixture_literal, EXPECTED)
        for item in self.source_fixture["records"]:
            self.assertEqual(
                item["expected_concept_iri"],
                f"https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/{item['value_code']}",
            )
            self.assertEqual(
                (
                    item["category_name"], item["morpheme_family"], item["morpheme_class"],
                    item["primary_source_id"], item["primary_section_id"],
                    item["primary_table_id"], item["primary_source_line"],
                    item["primary_source_url"], item["evidence_status"],
                ),
                (
                    "Configuration", "configuration", "CA_consonantal_exponent",
                    "NI-WEB-CH03", "NI-WEB-CH03:3.1", "NI-WEB-CH03:T003", "3239",
                    SOURCE_URL, "official_source_observed",
                ),
            )
        self.assertEqual(len(self.selection.source_records), 20)

    def test_projection_matches_literal_turtle_and_canonical_artifact(self) -> None:
        expected = Graph()
        expected.parse(FIXTURES / "configuration_expected.ttl", format="turtle")
        self.assertTrue(isomorphic(self.build.graph, expected))
        self.assertEqual(self.build.issues, ())
        self.assertEqual(len(self.build.emitted), 20)
        self.assertEqual(len(self.build.graph), 169)
        self.assertEqual(self.canonical.sha256, CANONICAL_SHA256)
        self.assertEqual(self.canonical.payload, (FIXTURES / "configuration_expected.nt").read_bytes())
        metadata = json.loads((FIXTURES / "configuration_expected.json").read_text())
        self.assertEqual(metadata["canonical_sha256"], CANONICAL_SHA256)
        self.assertEqual((metadata["concept_count"], metadata["triple_count"], metadata["held_issue_count"]), (20, 169, 0))

    def test_exact_concepts_labels_notes_and_notation(self) -> None:
        graph = self.build.graph
        concepts = set(graph.subjects(RDF.type, SKOS.Concept))
        expected_iris = {
            URIRef(f"https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/{code}")
            for code, *_ in EXPECTED
        }
        self.assertEqual(concepts, expected_iris)
        for code, label, form, realization_type, *_ in EXPECTED:
            subject = URIRef(f"https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/{code}")
            self.assertEqual(set(graph.objects(subject, SKOS.prefLabel)), {Literal(label, lang="en")})
            self.assertEqual(set(graph.objects(subject, SKOS.note)), {Literal(f"Configuration value {label}", lang="en")})
            self.assertEqual(
                set(graph.objects(subject, SKOS.notation)),
                {
                    Literal(code, datatype=URIRef(GRAMMAR_CODE_DATATYPE_IRI), normalize=False),
                    Literal(form, datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False),
                },
            )
            self.assertEqual(realization_type == "zero", code == "UPX")
        self.assertIn(Literal("∅", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False), graph.objects(URIRef("https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/UPX"), SKOS.notation))

    def test_scheme_collection_provenance_and_no_false_hierarchy(self) -> None:
        graph = self.build.graph
        scheme = URIRef(SCHEME)
        collection = URIRef(COLLECTION)
        locus = URIRef(LOCUS)
        self.assertIn((scheme, RDF.type, SKOS.ConceptScheme), graph)
        self.assertIn((collection, RDF.type, SKOS.Collection), graph)
        self.assertEqual(len(set(graph.objects(collection, SKOS.member))), 20)
        self.assertFalse(any(graph.triples((None, SKOS.broader, None))))
        self.assertFalse(any(graph.triples((None, SKOS.narrower, None))))
        semantic_subjects = set(graph.subjects(RDF.type, SKOS.Concept)) | {scheme, collection}
        for subject in semantic_subjects:
            self.assertEqual(set(graph.objects(subject, DCTERMS.source)), {locus})
        self.assertEqual(set(graph.objects(locus, DCTERMS.source)), {URIRef(SOURCE_URL)})
        self.assertEqual(set(graph.objects(locus, DCTERMS.identifier)), {Literal("source=NI-WEB-CH03;section=NI-WEB-CH03:3.1;table=NI-WEB-CH03:T003;line=3239")})
        self.assertEqual(set(graph.objects(URIRef(SOURCE_URL), DCTERMS.identifier)), {Literal("NI-WEB-CH03")})
        self.assertEqual(set(graph.objects(URIRef(SOURCE_URL), DCTERMS.bibliographicCitation)), {Literal("Chapter 3: Morphology")})

    def test_reordered_source_rows_produce_same_selection_and_digest(self) -> None:
        tables = []
        for table in self.closure.tables:
            rows = tuple(reversed(table.rows)) if table.name in {"morphemes_atomic", "source_assertions"} else table.rows
            tables.append(LoadedTable(table.name, table.columns, rows))
        closure = CompilerClosure(self.closure.manifest_version, tuple(tables))
        resolution = resolve_identities(closure)
        selection = select_configuration_resources(closure, resolution)
        build = build_core_graph(tuple(reversed(selection.resources)), SourceProjector(closure))
        self.assertEqual(selection.source_records, self.selection.source_records)
        self.assertEqual(canonicalize(build.graph).sha256, CANONICAL_SHA256)

    def test_selector_normalizes_multiple_source_forms_to_one_semantic_resource(self) -> None:
        table = self.closure.table("morphemes_atomic")
        mss = next(row for row in table.rows if row.get("category_code") == "CONFIGURATION" and row.get("value_code") == "MSS")
        values = dict(mss.values)
        values.update({"atomic_id": "ATOM-fixture-mss-second", "surface_form_raw": "ṭ", "surface_form_normalized": "ṭ", "allomorph_group_id": "AG-fixture-mss-second"})
        extra = FrozenRow(tuple((field, values[field]) for field in table.columns))
        tables = tuple(
            LoadedTable(item.name, item.columns, item.rows + (extra,)) if item.name == "morphemes_atomic" else item
            for item in self.closure.tables
        )
        closure = CompilerClosure(self.closure.manifest_version, tables)
        resolution = resolve_identities(closure)
        selection = select_configuration_resources(closure, resolution)
        mss_resource = next(resource for resource in selection.resources if resource.identity == Identity("grammar", ("CONFIGURATION", "MSS")))
        self.assertEqual(len(selection.source_records), 21)
        self.assertEqual(len(selection.resources), 20)
        self.assertEqual(len(mss_resource.source_records), 2)
        self.assertEqual({item.lexical_form for item in mss_resource.realizations}, {"t", "ṭ"})


if __name__ == "__main__":
    unittest.main()
