from __future__ import annotations

import csv
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

import lib.ithkuil.src.skos as _skos
BASE_SKOS = Path(next(iter(_skos.__path__))).resolve()
STAGED = Path(__file__).resolve().parents[1] / "src" / "skos"
VERIFY = Path(__file__).resolve().parents[3] / "_verify" / "lib" / "ithkuil" / "src" / "skos"
_skos.__path__.insert(0, str(STAGED))
if VERIFY.exists():
    _skos.__path__.append(str(VERIFY))

from lib.ithkuil.src.skos.allomorph_rule import (
    ALLOMORPH_DOMAIN, CONDITION, INPUT_PATTERN, INTERMEDIATE_PATTERN, OUTPUT_PATTERN,
    allomorph_rule_iri, project_allomorph_rules,
)
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.resolver import resolve_identities


LIB = BASE_SKOS.parents[1]
DATA = LIB / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def rows():
    with (DATA / "allomorph_rules.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class AllomorphRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.rows = rows()
        cls.before_identities = tuple(resource.identity for resource in resolve_identities(cls.closure).resources)
        cls.result = project_allomorph_rules(cls.closure, cls.rows)

    def test_current_rules_all_emit_without_semantic_concepts(self):
        self.assertEqual(len(self.rows), 19)
        self.assertEqual(len(self.result.records), 19)
        self.assertEqual(len(self.result.emitted_ids), 19)
        self.assertEqual(self.result.held_ids, ())
        self.assertEqual(self.result.issues, ())
        self.assertFalse(any(obj == SKOS.Concept for _, _, obj in self.result.graph))
        self.assertFalse(any(predicate in {SKOS.broader, SKOS.narrower, SKOS.related}
                             for _, predicate, _ in self.result.graph))

    def test_direct_and_intermediate_rules_preserve_exact_unicode_patterns(self):
        multi = next(record for record in self.result.records if record.rule_id == "ALLO-3100f4b83b2259")
        self.assertEqual((multi.input_pattern, multi.intermediate_pattern, multi.output_pattern),
                         ("ţbn", "tḑ", "ḑy"))
        subject = URIRef(multi.iri)
        self.assertIn((subject, INPUT_PATTERN, Literal("ţbn")), self.result.graph)
        self.assertIn((subject, INTERMEDIATE_PATTERN, Literal("tḑ")), self.result.graph)
        self.assertIn((subject, OUTPUT_PATTERN, Literal("ḑy")), self.result.graph)
        direct = next(record for record in self.result.records if record.rule_id == "ALLO-1189a0d351344c")
        self.assertEqual((direct.input_pattern, direct.intermediate_pattern, direct.output_pattern),
                         ("řř", "", "ňš"))
        self.assertFalse(list(self.result.graph.objects(URIRef(direct.iri), INTERMEDIATE_PATTERN)))

    def test_rule_domain_is_literal_source_reference_not_invented_group_link(self):
        self.assertEqual({record.domain for record in self.result.records}, {"C_A affix-complex"})
        for record in self.result.records:
            subject = URIRef(record.iri)
            self.assertIn((subject, ALLOMORPH_DOMAIN, Literal("C_A affix-complex")), self.result.graph)
        self.assertFalse(any(predicate == URIRef("https://github.com/Entif-AI/Bilqis-MLX/vocab/allomorphGroup")
                             for _, predicate, _ in self.result.graph))

    def test_rule_projection_does_not_change_resolved_semantic_identity_set(self):
        after = tuple(resource.identity for resource in resolve_identities(self.closure).resources)
        self.assertEqual(after, self.before_identities)

    def test_unknown_pattern_syntax_is_preserved_literally(self):
        changed = [dict(row) for row in self.rows]
        target = changed[0]
        target["input_pattern"] = "[FUTURE?]-ţ"
        result = project_allomorph_rules(self.closure, changed)
        self.assertIn(target["allomorph_rule_id"], result.emitted_ids)
        subject = URIRef(allomorph_rule_iri(target["allomorph_rule_id"]))
        self.assertIn((subject, INPUT_PATTERN, Literal("[FUTURE?]-ţ")), result.graph)

    def test_missing_required_field_is_held_without_partial_rule(self):
        changed = [dict(row) for row in self.rows]
        target = changed[0]; target["output_pattern"] = ""
        result = project_allomorph_rules(self.closure, changed)
        self.assertIn(target["allomorph_rule_id"], result.held_ids)
        self.assertTrue(any(issue.code == "ALLOMORPH_RULE_REQUIRED_FIELD_MISSING" for issue in result.issues))
        self.assertFalse(any(result.graph.triples((URIRef(allomorph_rule_iri(target["allomorph_rule_id"])), None, None))))

    def test_reorder_is_canonically_invariant(self):
        other = project_allomorph_rules(self.closure, reversed(self.rows))
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.records, self.result.records)

    def test_literal_rule_fixture_is_exact(self):
        expected = Graph().parse(FIXTURES / "skos_allomorph_rules_expected.nt", format="nt")
        actual = Graph()
        for rule_id in ("ALLO-08d9bb00e7a0dd", "ALLO-3100f4b83b2259", "ALLO-1189a0d351344c"):
            subject = URIRef(allomorph_rule_iri(rule_id))
            for triple in self.result.graph.triples((subject, None, None)):
                actual.add(triple)
        # Shared source locus and source-document triples are omitted from this literal
        # resource fixture; source projection is validated separately by exact source edge.
        for triple in list(actual):
            if str(triple[1]).endswith("source"):
                actual.remove(triple)
        self.assertEqual(canonicalize(actual), canonicalize(expected))


if __name__ == "__main__":
    unittest.main()
