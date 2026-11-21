"""Accepted history projects rich School evidence without inventing metrics."""
from dataclasses import replace
import unittest

import bilqis_mlx.control_plane.native_source as native_source
from bilqis_mlx.mission_control.contracts.dossier import CapabilityDossier

from .native_source_support import NativeSourceFixture


class AcceptedCapabilityDossierTests(NativeSourceFixture, unittest.TestCase):

    def test_accepted_history_projects_comparable_school_evidence(self):
        self.parent()
        self.publish_successor()
        history = list(native_source.authenticated_history(self.run))
        latest = history[-1]
        event = dict(latest.outbox[0])
        event["how_outcome"] = {
            "scores": [["A.NATIVE", 5, 7, 12]],
            "retained_steps": 3,
        }
        health = {
            "by_capability": {
                "A.NATIVE": {
                    "state": "MEASURED",
                    "first": {"correct": 5, "total": 12},
                    "latest": {"correct": 7, "total": 12},
                    "best": {"correct": 9, "total": 12},
                    "distance_to_mastery_state": "MEASURED",
                    "distance_to_mastery": 5,
                },
            },
        }
        history[-1] = replace(
            latest,
            outbox=(event,),
            learning_health_state=health,
        )

        dossiers = native_source._accepted_capability_dossiers(tuple(history), ())

        self.assertEqual(len(dossiers), 1)
        dossier = dossiers[0]
        self.assertIsInstance(dossier, CapabilityDossier)
        self.assertEqual(dossier.capability_id, "A.NATIVE")
        self.assertEqual(dossier.now.value, 7)
        self.assertEqual(dossier.top.value, 9)
        self.assertEqual(dossier.total.value, 12)
        self.assertEqual(dossier.retention.state.value, "UNKNOWN")
        values = {
            value.name: value.value.value
            for entry in dossier.entries
            for value in entry.values
            if value.value.value is not None
        }
        self.assertEqual(values["was"], 5)
        self.assertEqual(values["visits"], 1)
        self.assertEqual(values["retained_steps"], 3)
        self.assertEqual(values["strategy"], latest.teacher_state["last_visit"]["policy_key"])


if __name__ == "__main__":
    unittest.main()
