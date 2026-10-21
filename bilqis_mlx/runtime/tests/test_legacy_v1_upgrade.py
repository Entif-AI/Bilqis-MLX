"""A historically sealed v1 release is resume authority during v2 migration."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.factory.release import compile_factory_release, admit_factory_release
from bilqis_mlx.runtime.admission import (
    _persist_factory_release, _verified_legacy_upgrade_release,
    _verified_historical_cohort_release,
)
from bilqis_mlx.compatibility.assessment import sealed_v1_cohort_contract


class LegacyUpgradeTests(unittest.TestCase):
    def _stored(self, root):
        course, registry = synthetic_release_inputs()
        release = compile_factory_release(course, registry)
        path = _persist_factory_release(root, release)
        admission = admit_factory_release(
            release, student_sha256="b" * 64, optimizer_step=5,
            semantic_graph_sha256="a" * 64)
        state = {
            "factory_release_sha256": release.release_sha256,
            "factory_release_file": path,
            "factory_admission": asdict(admission),
            "semantic_graph_sha256": "a" * 64,
            "curriculum_mode": course.version,
            "school": {
                "course_digest": course.digest(),
                "current_student": {"sha256": "c" * 64, "optimizer_step": 6},
            },
        }
        return release, state

    def test_sealed_course_is_selected_even_when_reconstructed_course_has_drifted(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, state = self._stored(Path(tmp))
            pinned = _verified_legacy_upgrade_release(Path(tmp), state)
            self.assertEqual(pinned.course, original.course)
            self.assertEqual(pinned.course.digest(), state["school"]["course_digest"])
            grade = pinned.course.grades[0]
            adapter = pinned.source_adapter_map[pinned.capabilities[0].source_adapter_id]
            contract = sealed_v1_cohort_contract(pinned, grade)
            self.assertEqual(contract[0], grade.assessment_sha256)
            self.assertEqual(contract[2], adapter.cohort_generator)
            self.assertEqual(contract[3], adapter.cohort_code_sha256(contract[1]))

    def test_refuses_unsanctioned_school_digest_or_admission_rebinding(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, state = self._stored(Path(tmp))
            drifted = {**state, "school": {**state["school"],
                       "course_digest": "0" * 64}}
            with self.assertRaises(ValueError):
                _verified_legacy_upgrade_release(Path(tmp), drifted)
            drifted = {**state, "factory_admission": {**state["factory_admission"],
                       "course_sha256": "0" * 64}}
            with self.assertRaises(ValueError):
                _verified_legacy_upgrade_release(Path(tmp), drifted)
            drifted = {**state, "school": {**state["school"],
                       "current_student": {"sha256": "c" * 64, "optimizer_step": 4}}}
            with self.assertRaises(ValueError):
                _verified_legacy_upgrade_release(Path(tmp), drifted)

    def test_v2_receipt_can_verify_its_retained_historical_v1_exam(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, state = self._stored(Path(tmp))
            migrated = {
                **state,
                "school": {**state["school"], "course_digest": "e" * 64},
                "factory_release_sha256": "e" * 64,
                "factory_release_file": "factory-releases/" + "e" * 64 + ".json",
                "factory_admission_v2": {"factory_release_sha256": "e" * 64},
                "last_exam": {"cohort_sha256": "f" * 64},
            }
            historical = _verified_historical_cohort_release(Path(tmp), migrated)
            self.assertEqual(historical.release_sha256, original.release_sha256)
            tampered = {**migrated, "factory_admission": {
                **migrated["factory_admission"], "course_sha256": "0" * 64}}
            with self.assertRaises(ValueError):
                _verified_historical_cohort_release(Path(tmp), tampered)


if __name__ == "__main__":
    unittest.main()
