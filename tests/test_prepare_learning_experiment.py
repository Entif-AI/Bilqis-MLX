"""Cloning verifies file custody and cannot mutate original saved run."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.prepare_learning_experiment import execute, digest, ROOT


class PreparedExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="bilqis-fixture-run-")
        self.addCleanup(self.temp.cleanup)
        self.source=Path(self.temp.name)/"source"
        blob=self.source/"bundles/initial/model-and-own-adamw.safetensors"
        blob.parent.mkdir(parents=True)
        blob.write_bytes(b"fake-disposable-weights-and-adamw")
        state={"generation":7,"config":{"layers":6,"width":384,"heads":24},
               "teacher":{"events":123},"school":{"current_student":{
                   "filename":"bundles/initial","sha256":digest(blob),
                   "optimizer_step":99,"model_and_native_adamw":True}}}
        (self.source/"state.json").write_text(json.dumps(state))
        (ROOT/"runs").mkdir(exist_ok=True)
        self.destination=Path(tempfile.mkdtemp(prefix="learning-experiment-test-",
                    dir=ROOT/"runs"))/"cloned"
        # A one-off ignored directory; fixture owns only this destination.
        self.addCleanup(lambda: __import__("shutil").rmtree(
            self.destination.parent,ignore_errors=True))

    def test_read_only_plan_and_verified_copy_do_not_change_source(self):
        saved=(self.source/"state.json").read_bytes()
        report=execute(self.source,self.destination)
        self.assertFalse(report["cloned"])
        self.assertFalse(self.destination.exists())
        with patch("scripts.prepare_learning_experiment.trainer_guard"):
            clone=execute(self.source,self.destination,confirm=True,reserve_gib=0)
        self.assertTrue(clone["cloned"])
        self.assertEqual(clone["verified_files"],2)
        self.assertEqual((self.source/"state.json").read_bytes(),saved)
        self.assertEqual((self.destination/"state.json").read_bytes(),saved)
        self.assertEqual(digest(self.destination/"bundles/initial/model-and-own-adamw.safetensors"),
                         json.loads(saved)["school"]["current_student"]["sha256"])
        with self.assertRaisesRegex(ValueError,"DESTINATION"):
            execute(self.source,self.destination,confirm=True,reserve_gib=0)

    def test_changed_parent_file_is_rejected_before_copy(self):
        blob=self.source/"bundles/initial/model-and-own-adamw.safetensors"
        blob.write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError,"SHA_DRIFT"):
            execute(self.source,self.destination,confirm=True,reserve_gib=0)
        self.assertFalse(self.destination.exists())


if __name__=="__main__":
    unittest.main()
