import gzip
import hashlib
import json

from .base import StateDagCase
from bilqis_mlx.state_dag import head_summary, migrate_current_head, migrate_history, read_current, read_generation
from bilqis_mlx.cli import _inspect

class StateDagMigrationTests(StateDagCase):
    def test_migrates_legacy_head_without_rewriting_immutable_generation(self):
        receipt = self.receipt()
        legacy = __import__("json").dumps(receipt, sort_keys=True, separators=(",", ":"))
        (self.root / "state.json").write_text(legacy)
        immutable = self.root / "states/0000007.json"
        immutable.write_text(legacy)
        before = immutable.read_bytes()
        migrate_current_head(self.root)
        self.assertEqual(read_current(self.root), receipt)
        self.assertEqual(read_generation(self.root, 7), receipt)
        self.assertEqual(immutable.read_bytes(), before)
        self.assertEqual(head_summary(self.root)["mode"], "MERKLE_DAG")
        self.assertLess((self.root / "state.json").stat().st_size, 512)

    def test_cli_inspection_resolves_migrated_head(self):
        receipt = {
            "schema": "bilqis.mlx.human-grade-a-trainer/v1",
            "generation": 7,
            "result": "ACTIVE_GRADE_C",
            "school": {
                "active_grades": ["A", "B", "C"], "grade_index": 2,
                "current_student": {
                    "filename": "bundles/student", "model_and_native_adamw": True,
                    "optimizer_step": 123, "sha256": "1" * 64,
                },
                "stage": "MAIN", "visits": 9, "champions": {},
                "introduction_stage": 0,
            },
            "parameter_shapes": {"embedding.weight": [222, 8]},
            "config": {"vocab_size": 222},
            "teacher": {"events": 0, "strategies": {}},
            "last_exam": None,
            "mentor_epoch": None,
            "capability_best": {},
            "whole_student_peaks": [],
        }
        (self.root / "state.json").write_text(json.dumps(receipt))
        migrate_current_head(self.root, receipt)

        inspected = _inspect(self.root)

        self.assertEqual(inspected["status"], "ACTIVE_GRADE_C")
        self.assertEqual(inspected["grade"], "C")
        self.assertEqual(inspected["optimizer_step"], 123)

    def test_history_migration_replaces_full_snapshots_with_parent_linked_pointers(self):
        first = self.receipt(7)
        second = self.receipt(8)
        second["school"] = {"grade": "C", "queue": ["C.NUMBER"]}
        first_raw = json.dumps(first, sort_keys=True, separators=(",", ":")).encode()
        second_raw = json.dumps(second, sort_keys=True, separators=(",", ":")).encode()
        (self.root / "states/0000007.json").write_bytes(first_raw)
        with gzip.open(self.root / "states/0000008.json.gz", "wb") as stream:
            stream.write(second_raw)
        (self.root / "states/0000008.json.sha256").write_text(
            hashlib.sha256(second_raw).hexdigest() + "\n")
        (self.root / "state.json").write_bytes(second_raw)

        migrate_current_head(self.root, second)
        result = migrate_history(self.root)

        self.assertEqual(result["migrated_generations"], 2)
        self.assertEqual(read_generation(self.root, 7), first)
        self.assertEqual(read_generation(self.root, 8), second)
        self.assertEqual(read_current(self.root), second)
        self.assertFalse((self.root / "states/0000008.json.gz").exists())
        self.assertFalse((self.root / "states/0000008.json.sha256").exists())
        first_pointer = json.loads((self.root / "states/0000007.json").read_text())
        second_pointer = json.loads((self.root / "states/0000008.json").read_text())
        head_pointer = json.loads((self.root / "state.json").read_text())
        from bilqis_mlx.data_plane import data_plane
        second_node = json.loads(data_plane().get_node(second_pointer["node_sha256"]))
        self.assertEqual(second_node["parent_sha256"], first_pointer["node_sha256"])
        self.assertEqual(head_pointer, second_pointer)
