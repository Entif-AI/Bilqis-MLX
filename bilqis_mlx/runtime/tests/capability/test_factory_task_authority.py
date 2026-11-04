"""Factory C04 task authority keeps evaluator truth outside source lowering."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.tests.test_teaching import closed_source_fixture
from bilqis_mlx.runtime.factory_task_authority import (
    FactoryTaskAuthority, _source_view,
)


class FactoryTaskAuthorityTests(unittest.TestCase):
    def test_source_view_removes_evaluator_owned_fields(self):
        row = {
            "id": "case-1", "capability": "Z.C0", "tokens": [1, 2],
            "source_family_id": "fresh-family", "episode_id": "fresh-episode",
            "gold": "TRUE", "native_output": {"token_id": 2},
            "auxiliary_labels": {"role": "subject"},
            "answer": "TRUE", "label": "TRUE", "expected": "TRUE",
            "expected_answer": "TRUE", "score": 1,
            "oracle_result": {"correct": True},
        }

        visible = _source_view(row)

        self.assertEqual(visible, {
            "id": "case-1", "capability": "Z.C0", "tokens": [1, 2],
            "source_family_id": "fresh-family", "episode_id": "fresh-episode",
        })

    def test_caller_cannot_construct_factory_task_authority(self):
        with self.assertRaises(BilqisError):
            FactoryTaskAuthority()

    def test_registered_source_task_lowerer_must_be_callable(self):
        _, _, sources, _, _ = closed_source_fixture()
        registered = sources.require("fixture.z-generator/v1", "fixture.z-oracle/v1")
        with self.assertRaises(ValueError):
            SourceAdapterRegistry((replace(registered, task_goal="caller-selected"),))


if __name__ == "__main__":
    unittest.main()
