import json
from unittest.mock import patch

from .base import StateDagCase
from bilqis_mlx.state_dag import HEAD_SCHEMA, migrate_current_head, persist, read_current, read_current_fields, read_generation, read_generation_fields

class StateDagFieldTests(StateDagCase):
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
