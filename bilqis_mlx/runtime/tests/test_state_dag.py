import os
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.state_dag import (
    HEAD_SCHEMA, head_summary, migrate_current_head, migrate_history, persist,
    read_current, read_current_fields, read_generation, read_generation_fields,
)
from bilqis_mlx.cli import _inspect


class StateDagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "states").mkdir()
        self.previous_plane = os.environ.get("BILQIS_DATA_PLANE")
        os.environ["BILQIS_DATA_PLANE"] = str(self.root / "plane.sqlite3")
        from bilqis_mlx.data_plane import close_data_planes
        close_data_planes()

    def tearDown(self):
        from bilqis_mlx.data_plane import close_data_planes
        close_data_planes()
        if self.previous_plane is None:
            os.environ.pop("BILQIS_DATA_PLANE", None)
        else:
            os.environ["BILQIS_DATA_PLANE"] = self.previous_plane
        self.temp.cleanup()

    def receipt(self, generation=7):
        misses = [
            {"id": "b" * 64, "capability": "C.NUMBER", "gold": 1},
            {"id": "a" * 64, "capability": "C.COUNT", "gold": 0},
        ]
        misses.sort(key=lambda row: (row["capability"], row["id"]))
        return {
            "schema": "school/v1", "generation": generation,
            "school": {"grade": "C", "queue": ["C.COUNT"]},
            "teacher_misses": misses,
            "teacher_miss_exposures": {row["id"]: 2 for row in misses},
            "championship_epoch_history": [{"schema": "epoch/v1", "n": 1}],
            "large": {"payload": "x" * 40000},
        }

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

    def test_successor_node_shares_unchanged_objects_and_roundtrips(self):
        first = self.receipt()
        (self.root / "state.json").write_text(__import__("json").dumps(first))
        migrate_current_head(self.root, first)
        successor = self.receipt(8)
        successor["school"] = {"grade": "C", "queue": ["C.NUMBER"]}
        successor["teacher_misses"].append(
            {"id": "c" * 64, "capability": "C.COUNT", "gold": 1})
        successor["teacher_misses"].sort(key=lambda row: (row["capability"], row["id"]))
        successor["teacher_miss_exposures"]["c" * 64] = 0
        persist(self.root, successor)
        self.assertEqual(read_current(self.root), successor)
        self.assertEqual(read_generation(self.root, 8), successor)
        pointer = __import__("json").loads((self.root / "state.json").read_text())
        self.assertEqual(pointer["schema"], HEAD_SCHEMA)
        from bilqis_mlx.data_plane import data_plane
        node = __import__("json").loads(data_plane().get_node(pointer["node_sha256"]))
        self.assertIsNotNone(node["parent_sha256"])
        self.assertEqual(node["fields"]["teacher_misses"]["count"], 3)

    def test_teacher_miss_v2_reuses_unchanged_prefix_shards(self):
        first = self.receipt()
        first["teacher_misses"] = [
            {"id": "aa" + "0" * 62, "capability": "C.COUNT", "gold": 0},
            {"id": "bb" + "0" * 62, "capability": "C.COUNT", "gold": 1},
        ]
        first["teacher_miss_exposures"] = {
            row["id"]: 1 for row in first["teacher_misses"]}
        (self.root / "state.json").write_text(json.dumps(first))
        migrate_current_head(self.root, first)
        from bilqis_mlx.data_plane import data_plane
        first_pointer = json.loads((self.root / "state.json").read_text())
        first_node = json.loads(data_plane().get_node(first_pointer["node_sha256"]))

        second = self.receipt(8)
        second["teacher_misses"] = [
            *first["teacher_misses"],
            {"id": "cc" + "0" * 62, "capability": "C.COUNT", "gold": 0},
        ]
        second["teacher_miss_exposures"] = {
            row["id"]: 1 for row in second["teacher_misses"]}
        persist(self.root, second)
        second_pointer = json.loads((self.root / "state.json").read_text())
        second_node = json.loads(data_plane().get_node(second_pointer["node_sha256"]))

        before = first_node["fields"]["teacher_misses"]
        after = second_node["fields"]["teacher_misses"]
        self.assertEqual(before["kind"], "teacher-misses/v2")
        self.assertEqual(after["kind"], "teacher-misses/v2")
        self.assertEqual(before["shards"]["C.COUNT"]["aa"],
                         after["shards"]["C.COUNT"]["aa"])
        self.assertEqual(before["shards"]["C.COUNT"]["bb"],
                         after["shards"]["C.COUNT"]["bb"])
        self.assertIn("cc", after["shards"]["C.COUNT"])
        self.assertEqual(read_current(self.root), second)

    def test_teacher_v2_reuses_unchanged_causal_contexts(self):
        first = self.receipt()
        first["teacher"] = {
            "events": 7,
            "strategies": {"main": {"wins": 1}},
            "causal_experiment": {
                "version": "v1",
                "contexts": {
                    "A|MAIN": {"attempts": [1, 2, 3]},
                    "B|MAIN": {"attempts": [4, 5, 6]},
                },
                "negative_archetypes": {},
            },
        }
        (self.root / "state.json").write_text(json.dumps(first))
        migrate_current_head(self.root, first)
        from bilqis_mlx.data_plane import data_plane
        first_pointer = json.loads((self.root / "state.json").read_text())
        first_node = json.loads(data_plane().get_node(first_pointer["node_sha256"]))

        second = self.receipt(8)
        second["teacher"] = json.loads(json.dumps(first["teacher"]))
        second["teacher"]["events"] = 8
        second["teacher"]["causal_experiment"]["contexts"]["B|MAIN"] = {
            "attempts": [4, 5, 6, 7]}
        persist(self.root, second)
        second_pointer = json.loads((self.root / "state.json").read_text())
        second_node = json.loads(data_plane().get_node(second_pointer["node_sha256"]))

        before = first_node["fields"]["teacher"]
        after = second_node["fields"]["teacher"]
        self.assertEqual(before["kind"], "teacher/v2")
        before_contexts = before["fields"]["causal_experiment"]["fields"]["contexts"]
        after_contexts = after["fields"]["causal_experiment"]["fields"]["contexts"]
        self.assertEqual(before_contexts["items"]["A|MAIN"],
                         after_contexts["items"]["A|MAIN"])
        self.assertNotEqual(before_contexts["items"]["B|MAIN"],
                            after_contexts["items"]["B|MAIN"])
        self.assertEqual(read_current(self.root), second)

    def test_partial_current_read_decodes_only_requested_fields(self):
        receipt = self.receipt()
        (self.root / "state.json").write_text(json.dumps(receipt))
        migrate_current_head(self.root, receipt)
        import bilqis_mlx.state_dag as state_dag

        with patch.object(state_dag, "_decode_field",
                          wraps=state_dag._decode_field) as decode:
            selected = read_current_fields(self.root, ("school",))

        self.assertEqual(selected, {"school": receipt["school"]})
        self.assertEqual(decode.call_count, 1)

    def test_partial_generation_read_decodes_only_requested_fields(self):
        receipt = self.receipt()
        (self.root / "state.json").write_text(json.dumps(receipt))
        migrate_current_head(self.root, receipt)
        persist(self.root, receipt)
        import bilqis_mlx.state_dag as state_dag

        with patch.object(state_dag, "_decode_field",
                          wraps=state_dag._decode_field) as decode:
            selected = read_generation_fields(self.root, 7, ("school",))

        self.assertEqual(selected, {"school": receipt["school"]})
        self.assertEqual(decode.call_count, 1)

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


if __name__ == "__main__":
    unittest.main()
