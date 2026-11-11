"""Real-artifact C08 preflight that stops immediately before expensive gradients."""
from pathlib import Path
from tempfile import TemporaryDirectory

from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.factory_task_authority import (
    bind_factory_task_compiled_batch,
    factory_task_authority,
    factory_task_training_goal,
)

from .factory_training_bridge_support import FactoryTrainingBridgeFixture
from .factory_training_execution_support import (
    assert_prepared_logical_rows, draw, observation, publish, split_budget,
)


class FactoryTrainingPreflightTests(FactoryTrainingBridgeFixture):
    def test_split_real_rows_reaches_gradient_boundary(self):
        rows, _ = draw(self, "A.IDENTITY", 37117, 2)
        with TemporaryDirectory() as run_dir_value:
            run_dir = Path(run_dir_value)
            publish(self, run_dir)
            source_context = self.accepted_source_context(run_dir)
            parent = load_accepted_generation(run_dir)
            prepared = self.prepare("A.IDENTITY", 37117, 2)[1]
            row_ids = tuple(row["id"] for row in rows)
            assert_prepared_logical_rows(self, prepared, row_ids)
            _, delivery_observation = observation(
                run_dir, "A.IDENTITY", rows, 37117)
            delivery_observation.__post_init__()
            split_budget(parent, prepared)
            for compiled in prepared.compiled_rows:
                authority = factory_task_authority(source_context, compiled)
                self.assertEqual(
                    authority.training_authority_sha256,
                    compiled.training_authority.digest)
                bound = bind_factory_task_compiled_batch(compiled, authority)
                goal = factory_task_training_goal(source_context, bound, authority)
                self.assertEqual(goal.goal_id, authority.source_row_id)
