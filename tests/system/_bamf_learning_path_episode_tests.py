"""C13.1 live source and TaskGoal authority contracts."""
from pathlib import Path
import unittest

from scripts.bamf.c13.episode_source import (
    CAPABILITY,
    GENERATOR_ID,
    ORACLE_ID,
    PROVIDER_ID,
    episode_factory_release,
    implementation_digest,
    registered_episode_lowerer,
)


class BamfLearningPathEpisodeSourceTests(unittest.TestCase):
    def test_live_episode_provider_compiles_and_redraws_through_factory(self):
        from bilqis_mlx.runtime.source_execution import SourceExecutionContext
        from bilqis_mlx.source_adapters.school import live_source_registry

        release, graph, sources, answers = episode_factory_release()
        owner = live_source_registry().require(GENERATOR_ID, ORACLE_ID)
        self.assertEqual(owner.descriptor.adapter_id, PROVIDER_ID)
        self.assertEqual(owner.descriptor.implementation_sha256, implementation_digest())
        context = SourceExecutionContext(
            release,
            graph,
            (Path(__file__).resolve().parents[2] / "vendor/legacy-v16").resolve(),
            sources,
            answers,
        )
        rows = tuple(context.draw_rows(seed=31, capability=CAPABILITY, each=4))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(
            sources.resolve_owner(row["generator"]).check(row, graph=graph)
            for row in rows))
        authority = context.bind_rows(rows, seed=31, capability=CAPABILITY, each=4)
        self.assertEqual(authority.release_sha256, release.release_sha256)
        self.assertEqual(authority.source_family_id, "bamf.c13.episode-binding/v1")

    def test_episode_lowerer_is_gold_blind_and_resolves_binding_by_actor_identity(self):
        from bilqis_mlx.runtime.factory_task_authority import _source_view
        from bilqis_mlx.runtime.source_execution import SourceExecutionContext

        release, graph, sources, answers = episode_factory_release()
        context = SourceExecutionContext(release, graph, None, sources, answers)
        row = context.draw_rows(seed=17, capability=CAPABILITY, each=1)[0]
        capability = release.execution_plan.capability_map[CAPABILITY]
        lowerer = registered_episode_lowerer()
        goal, binding = lowerer.lower(
            _source_view(row), semantic_release="e" * 64, capability=capability)
        resolved = lowerer.resolve(
            row, semantic_release="e" * 64, capability=capability)

        self.assertEqual(goal.output_signature, "Number")
        self.assertTrue(all(
            node.operands[0] is None
            for node in goal.expression_or_holes.nodes
            if node.node_id.startswith("select-")))
        self.assertEqual(len(binding.operands), 6)
        selected = tuple(
            node.operands[0].source_handle
            for node in resolved.expression_or_holes.nodes
            if node.node_id.startswith("select-"))
        self.assertTrue(selected)
        self.assertTrue(all(handle.startswith("source:c13:") for handle in selected))
        self.assertNotIn(str(row["gold"]), selected)

    def test_live_lowerer_registration_matches_exact_provider_digest(self):
        from bilqis_mlx.source_adapters import task_goal_registry

        lowerer = registered_episode_lowerer()
        selected = task_goal_registry.require_task_goal_lowerer(
            lowerer.provider_id, lowerer.provider_implementation_sha256)
        self.assertEqual(selected, lowerer)


__all__ = ("BamfLearningPathEpisodeSourceTests",)
