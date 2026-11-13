"""B10.4 AnswerPlan/v2 and B01-owned readout tensor census."""
import unittest

import mlx.core as mx

from bilqis_mlx.learning.atlas_readout.control import ControlAction as C
from bilqis_mlx.learning.atlas_readout.plan import DecisionKind as K, DecisionSpec as D
from bilqis_mlx.learning.atlas_readout.tests.plan_helpers import concept, plan
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents,
    Initializer,
    ModelTopologySpecV2,
    expected_bamf_shapes,
    initialize_bamf_parameter,
)


class ReadoutParameterContractTests(unittest.TestCase):
    @staticmethod
    def extents():
        return GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)

    def test_readout_census_is_exact_projection_of_b01_ledger(self):
        from bilqis_mlx.learning.atlas_readout.parameters import readout_parameter_specs

        spec, extents = ModelTopologySpecV2(), self.extents()
        projected = readout_parameter_specs(spec, extents)
        b01 = tuple(
            item for item in expected_bamf_shapes(spec, extents)
            if item.name.startswith("readout."))
        self.assertEqual(projected, b01)
        self.assertEqual(
            tuple(item.name for item in projected),
            (
                "readout.state_norm",
                "readout.output_norm",
                "readout.query",
                "readout.key",
                "readout.value",
                "readout.output",
                "readout.feedback",
                "readout.role_query",
                "readout.control",
                "readout.control_bias",
                "readout.epistemic",
                "readout.epistemic_bias",
                "readout.salience.impact",
                "readout.salience_bias.impact",
                "readout.salience.exigency",
                "readout.salience_bias.exigency",
                "readout.salience.novelty",
                "readout.salience_bias.novelty",
            ),
        )

    def test_readout_view_rejects_missing_extra_and_wrong_shape(self):
        from bilqis_mlx.errors import BilqisError
        from bilqis_mlx.learning.atlas_readout.parameters import (
            bind_readout_parameters,
            readout_parameter_specs,
        )

        spec, extents = ModelTopologySpecV2(), self.extents()
        values = {
            item.name: mx.array(
                initialize_bamf_parameter(item, run_seed=0), dtype=mx.float32)
            for item in readout_parameter_specs(spec, extents)
        }
        bound = bind_readout_parameters(values, spec, extents)
        self.assertEqual(tuple(bound), tuple(values))
        for changed in (
            {key: value for key, value in values.items() if key != "readout.feedback"},
            {**values, "features.role": mx.zeros((512, 128), dtype=mx.float32)},
            {**values, "readout.feedback": mx.zeros((767, 768), dtype=mx.float32)},
        ):
            with self.subTest(keys=tuple(changed)), self.assertRaises(BilqisError):
                bind_readout_parameters(changed, spec, extents)

    def test_readout_owns_no_shared_feature_depth_or_identity_tensor(self):
        from bilqis_mlx.learning.atlas_readout.parameters import readout_parameter_specs

        names = tuple(
            item.name for item in readout_parameter_specs(
                ModelTopologySpecV2(), self.extents()))
        self.assertTrue(names)
        self.assertTrue(all(name.startswith("readout.") for name in names))
        self.assertFalse(any(
            name.startswith(("features.", "depth.", "identity.", "motif.", "plastic."))
            for name in names))

    def test_answer_plan_v2_executes_dependency_order_with_b01_budget(self):
        answer_plan = plan((
            D("control", "agent", 0, K.CONTROL, (C.EMIT_VALUE, C.EMIT_UNKNOWN)),
            D("value", "agent", 0, K.VALUE, (concept(),), ("control",)),
            D("end", None, 0, K.CONTROL, (C.END_FRAME,), ("value",)),
        ))
        self.assertEqual(answer_plan.schema_version, "bilqis.mlx.answer-plan/v2")
        self.assertEqual(answer_plan.execution_order, ("control", "value", "end"))
        self.assertLessEqual(answer_plan.maximum_decisions, 64)
        self.assertLessEqual(
            answer_plan.input_prefix_end + answer_plan.position_budget,
            ModelTopologySpecV2.context)

    def test_readout_initializers_remain_b01_authority(self):
        from bilqis_mlx.learning.atlas_readout.parameters import readout_parameter_specs

        rows = {item.name: item for item in readout_parameter_specs(
            ModelTopologySpecV2(), self.extents())}
        self.assertIs(rows["readout.feedback"].initializer, Initializer.MATRIX)
        self.assertIs(rows["readout.control_bias"].initializer, Initializer.ZERO)
        self.assertIs(rows["readout.state_norm"].initializer, Initializer.ONE)


if __name__ == "__main__":
    unittest.main()
