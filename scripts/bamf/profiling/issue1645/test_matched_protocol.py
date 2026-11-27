import unittest

from scripts.bamf.profiling.issue1645.matched_protocol import (
    MATCHED_FIELDS, MECHANISMS, prepare_pair, validate_comparison,
)
from scripts.bamf.profiling.issue1645.reservation import prepare
from scripts.bamf.profiling.issue1645.test_reservation import fixture


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.reservation = prepare(fixture())
        self.common = {key: "fixture" for key in MATCHED_FIELDS}
        self.common.update(reservation_sha256=self.reservation["reservation_sha256"],
                           bindings=self.reservation["bindings"], training_seed=1,
                           exam_seed=2, exam_each=12, visit_horizon=16, primary_rows=32,
                           support_rows=5, wall_seconds=360, max_seconds=480,
                           exam_max_seconds=300, worker_count=1)

    def test_all_mechanisms_are_non_authorizing(self):
        for mechanism in MECHANISMS:
            pair = prepare_pair(self.reservation, self.common, mechanism, {})
            self.assertFalse(pair["launch_authorized"])
            self.assertIsNone(pair["evidence_reference"])

    def test_mismatch_and_unrealized_guidance_fail_closed(self):
        pair = prepare_pair(self.reservation, self.common, "distillation",
                            {"authorized_adviser_and_actual_guidance": "fixture"})
        common = dict(common=self.common, exclusion_enforced=True,
                      exam_count=72, actual_wall_seconds=360, retained_gain=2)
        control = dict(common, mechanism=pair["control"], actual_guidance_steps=0)
        treatment = dict(common, mechanism=pair["treatment"], actual_guidance_steps=0)
        with self.assertRaisesRegex(ValueError, "guidance not realized"):
            validate_comparison(pair, control, treatment)
        treatment["actual_guidance_steps"] = 3
        self.assertFalse(validate_comparison(pair, control, treatment)["certification_granted"])
        treatment["common"] = dict(self.common, observer_mode="changed")
        with self.assertRaisesRegex(ValueError, "unmatched common"):
            validate_comparison(pair, control, treatment)

    def test_partial_exam_and_unenforced_exclusion(self):
        pair = prepare_pair(self.reservation, self.common, "reservation",
                            {"source_complete_groups_and_exclusion": "fixture"})
        arm = dict(common=self.common, mechanism=pair["control"],
                   exclusion_enforced=True, exam_count=71, actual_wall_seconds=360)
        with self.assertRaisesRegex(ValueError, "partial exam"):
            validate_comparison(pair, arm, arm)
        arm["exclusion_enforced"] = False
        with self.assertRaisesRegex(ValueError, "exclusion not enforced"):
            validate_comparison(pair, arm, arm)
