"""A declarative unknown grade uses the same durable runtime admission gate."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.runtime.admission import _factory_admission, _require_factory_admission


class RuntimeAdmissionTests(unittest.TestCase):
    def setUp(self):
        course, self.registry = synthetic_release_inputs()
        grade = course.grades[0]
        caps = tuple(replace(cap, id=cap.id.replace("A.", "Z.")) for cap in grade.capabilities)
        self.course = replace(course, grades=(replace(
            grade, id="Z", capabilities=caps,
            exam_item_counts=tuple((cap.id, 4) for cap in caps)),))
        self.student = Checkpoint("a" * 64, "bundles/fixture", 7, True)

    def admission(self, root):
        release, path, admission = _factory_admission(
            root, self.course, self.student, "b" * 64, registry=self.registry)
        receipt = {"factory_release_sha256": release.release_sha256,
                   "factory_release_file": path, "factory_admission": asdict(admission),
                   "semantic_graph_sha256": "b" * 64,
                   "school": {"current_student": asdict(self.student)}}
        return release, receipt

    def test_synthetic_grade_admits_and_reads_back_without_a_live_grade_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release, receipt = self.admission(root)
            restored = _require_factory_admission(
                root, json.loads(json.dumps(receipt)), self.course, registry=self.registry)
            self.assertEqual(restored, release)
            self.assertEqual(restored.grades[0].grade_id, "Z")

    def test_schema_tamper_and_same_step_student_substitution_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, receipt = self.admission(root)
            receipt["factory_admission"]["student_sha256"] = "c" * 64
            with self.assertRaisesRegex(ValueError, "FACTORY_ADMISSION_BASELINE_DRIFT"):
                _require_factory_admission(root, receipt, self.course, registry=self.registry)
            receipt["factory_admission"]["student_sha256"] = self.student.sha256
            path = root / receipt["factory_release_file"]
            payload = json.loads(path.read_text())
            payload["schema"] = "unrelated.schema/v999"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "FACTORY_RELEASE_DURABLE_SCHEMA_INVALID"):
                _require_factory_admission(root, receipt, self.course, registry=self.registry)
