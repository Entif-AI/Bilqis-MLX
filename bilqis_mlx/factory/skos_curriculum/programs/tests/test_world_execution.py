"""Actual world source batches use the same binding under different grade labels."""
from unittest import TestCase
from dataclasses import replace

from bilqis_mlx.factory.model import CapabilityDefinition, ConstructionProgram
from bilqis_mlx.factory.skos_curriculum.registry import (
    bind_existing_family_program, default_family_program_registry, execute_bound_family_program,
)
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters.copular import CAPABILITY, GENERATOR, ORACLE, SYMBOL
from bilqis_mlx.source_adapters.copular_curriculum import expanded_graph
from bilqis_mlx.source_adapters.school import live_source_registry


class WorldProgramExecutionTests(TestCase):
    def execute(self, capability_id, grade):
        sources = live_source_registry()
        programs = default_family_program_registry()
        family = programs.require("source_world_fixture")
        capability = CapabilityDefinition(capability_id, grade, (),
            "source.ithkuil-reference-identity/v1", ORACLE, ("binary",))
        program = ConstructionProgram(capability_id, capability.source_adapter_id, GENERATOR, ORACLE, ())
        bound = bind_existing_family_program(family, capability, program, sources)
        graph = expanded_graph(registry_graph())
        return execute_bound_family_program(
            programs, bound,
            source_registry=sources,
            construct_kwargs={"source_root": None, "graph": graph, "seed": 17, "each": 12,
                              "capability": capability_id, "generator_id": GENERATOR, "oracle_id": ORACLE},
            check_kwargs={"graph": graph, "generator_id": GENERATOR, "oracle_id": ORACLE})

    def test_registered_world_program_checks_every_row_of_its_real_batch(self):
        artifact = self.execute(CAPABILITY, "D")
        rows = artifact.rows
        self.assertEqual(len(rows), 12)
        self.assertEqual({row["root"] for row in rows}, {SYMBOL})
        self.assertEqual({row["gold"] for row in rows}, {"TRUE", "FALSE"})
        self.assertEqual(artifact.learning_state, "LEARNING_UNVERIFIED")

    def test_same_source_family_runs_under_another_grade_without_semantic_change(self):
        ordinary = self.execute(CAPABILITY, "D")
        other = self.execute("Z.COPULAR_IDENTITY", "Z")
        self.assertEqual(ordinary.rows, other.rows)
        self.assertEqual(other.capability_id, "Z.COPULAR_IDENTITY")
        self.assertEqual({row["capability"] for row in other.rows}, {CAPABILITY})

    def test_independent_checker_rejects_a_tampered_row_and_foreign_factory_label(self):
        artifact = self.execute("Z.COPULAR_IDENTITY", "Z")
        graph = expanded_graph(registry_graph())
        source = live_source_registry().require(GENERATOR, ORACLE)
        checker = default_family_program_registry().require("source_world_fixture").check
        self.assertTrue(checker(source, artifact, graph=graph, capability_id="Z.COPULAR_IDENTITY"))
        changed = {**artifact.rows[1], "gold": "wrong"}
        bad = replace(artifact, rows=(artifact.rows[0], changed, *artifact.rows[2:]))
        self.assertFalse(checker(source, bad, graph=graph, capability_id="Z.COPULAR_IDENTITY"))
        self.assertFalse(checker(source, artifact, graph=graph, capability_id=CAPABILITY))

    def test_source_batch_cannot_claim_learning(self):
        from bilqis_mlx.errors import BilqisError
        with self.assertRaises(BilqisError):
            replace(self.execute(CAPABILITY, "D"), learning_state="LEARNING_VERIFIED")
