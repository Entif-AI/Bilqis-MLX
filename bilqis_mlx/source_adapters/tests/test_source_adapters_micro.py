"""Source-oracled integration tests for the generic functional AST."""
from __future__ import annotations

from pathlib import Path
import unittest

from bilqis_mlx.semantics import TypedError
from bilqis_mlx.source_adapters import bind_source_catalog, from_micro_query
from bilqis_mlx.verification import verify
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_b_oracle import CONNECTIVES, evaluate as boolean_oracle, operand_truth
from bilqis_mlx.live_grade_b import _encode_logic_record, _logic_source, draw_connectives
from bilqis_mlx.registry_ast import load_registry
from bilqis_mlx.token_atlas import ORIGINAL_GRAPH_DIGEST


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "vendor" / "legacy-v16"
SNAPSHOT = ROOT / "docs/provenance/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json"
ORIGINAL_OPERANDS = ("micro.compare.EQ", "micro.relation.PARENT",
                     "micro.relation.LINK")


class MicroSource:
    identity = "original-micro-source"

    def __init__(self, micro, world):
        self.micro = micro
        self.world = world

    def invoke(self, operation, values, world_contract):
        if world_contract != "micro":
            raise ValueError("SOURCE_MICRO_WORLD_MISMATCH")
        domain, name = operation.symbol.rsplit(".", 1)
        if domain == "cogal.operator":
            expr = self.micro.boolean.apply(
                name, *(self.micro.boolean.literal(v) for v in values))
            return self.micro.boolean.evaluate(expr, {})
        if domain == "micro.compare":
            expr = self.micro.compare(name, *(self.micro.entity(v) for v in values))
        elif domain == "micro.relation":
            expr = self.micro.relation(name, *(self.micro.entity(v) for v in values))
        else:
            raise ValueError("SOURCE_MICRO_UNKNOWN_ROOT")
        record = self.micro.record(self.world, expr)
        answer = self.micro.evaluate(record)
        if answer != self.micro.independent_evaluate(record):
            raise ValueError("SOURCE_MICRO_ORACLE_CONFLICT")
        return answer == "TRUE"


class IndependentFiniteSymbolic:
    identity = "independent-finite-model-sympy"

    def __init__(self, world):
        import sympy
        self.world = world
        self.logic = {
            "NOT": sympy.Not, "AND": sympy.And, "OR": sympy.Or,
            "XOR": sympy.Xor, "IMPLIES": sympy.Implies,
            "IFF": sympy.Equivalent,
        }

    def invoke(self, operation, values, world_contract):
        if world_contract != "micro":
            raise ValueError("INDEPENDENT_FINITE_WORLD_MISMATCH")
        domain, name = operation.symbol.rsplit(".", 1)
        if domain == "cogal.operator":
            return bool(self.logic[name](*values))
        if domain == "micro.compare":
            node = {"kind": "compare", "operator": name, "args": [
                {"kind": "entity", "name": v} for v in values]}
        elif domain == "micro.relation":
            node = {"kind": "relation", "name": name, "args": [
                {"kind": "entity", "name": v} for v in values]}
        else:
            raise ValueError("INDEPENDENT_FINITE_UNKNOWN_ROOT")
        return operand_truth(self.world, node)


class MicroSourceAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.micro, _, cls.graph, _, _ = read_sources(SOURCE_ROOT)
        cls.tokens = load_registry(SNAPSHOT).tokens
        identities = set(ORIGINAL_OPERANDS)
        identities.update("cogal.operator." + n for n in CONNECTIVES)
        cls.catalog = bind_source_catalog(
            cls.tokens, cls.graph, identities,
            historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)
        for identity in identities:
            operation = cls.catalog.resolve_external_name(identity)
            if cls.graph["tokens"][operation.token_index] != identity:
                raise AssertionError("Pinned original token identity drift")

    def test_real_generated_b_records_use_direct_boolean_source_ast(self):
        rows = draw_connectives(SOURCE_ROOT, self.graph, seed=2026101619)
        self.assertEqual(len(rows), 72)
        logic = _logic_source(SOURCE_ROOT)
        for row in rows:
            record = row["record"]
            self.assertEqual(record["task"], "evaluate")
            self.assertNotIn("world", record)
            self.assertEqual(row["gold"],
                             boolean_oracle(record, row["capability"]))
            self.assertEqual(row["tokens"],
                             _encode_logic_record(logic, record, self.graph))

    def test_unrecognized_source_forms_never_gain_guessed_gold(self):
        with self.assertRaisesRegex(TypedError, "UNKNOWN_EXTERNAL_ALIAS"):
            from_micro_query(self.catalog, {"kind": "apply",
                            "operator": "UNADMITTED",
                            "args": [{"kind": "literal", "value": True}]})
        with self.assertRaisesRegex(TypedError, "UNSUPPORTED_SOURCE_NODE"):
            from_micro_query(self.catalog, {"kind": "invented_morphology"})
        with self.assertRaisesRegex(TypedError, "OPERATOR_SHAPE"):
            from_micro_query(self.catalog, {"kind": "relation", "name": "PARENT"})


if __name__ == "__main__":
    unittest.main()
