import json
from unittest.mock import patch

from .base import StateDagCase
from bilqis_mlx.state_dag import migrate_current_head, persist, read_current, read_generation

class StateDagPersistenceTests(StateDagCase):
    def test_public_symbols_keep_historical_module_identity(self):
        import bilqis_mlx.state_dag as state_dag
        names = ("StateDagError", "migrate_current_head", "persist",
                 "head_summary", "migrate_history", "main")
        self.assertEqual(
            {name: getattr(state_dag, name).__module__ for name in names},
            {name: "bilqis_mlx.state_dag" for name in names},
        )

    def test_facade_durable_patch_intercepts_latest_pointer_write(self):
        first = self.receipt()
        (self.root / "state.json").write_text(json.dumps(first))
        migrate_current_head(self.root, first)
        successor = self.receipt(8)
        import bilqis_mlx.state_dag as state_dag
        original = state_dag._durable
        observed = []

        def interrupt(path, value, **kwargs):
            observed.append(path.name)
            if path.name == "state.json":
                raise RuntimeError("pointer interrupted")
            return original(path, value, **kwargs)

        with patch.object(state_dag, "_durable", side_effect=interrupt):
            with self.assertRaisesRegex(RuntimeError, "pointer interrupted"):
                persist(self.root, successor)

        self.assertIn("state.json", observed)

    def test_orphan_dag_successor_replays_from_verified_legacy_head(self):
        legacy = self.receipt(7)
        raw = json.dumps(legacy)
        (self.root / "states/0000007.json").write_text(raw)
        (self.root / "state.json").write_text(raw)
        successor = {**legacy, "generation": 8}
        persist(self.root, successor)
        expected = (self.root / "state.json").read_bytes()
        (self.root / "state.json").write_text(raw)
        self.assertEqual(persist(self.root, successor), successor)
        self.assertEqual((self.root / "state.json").read_bytes(), expected)
        changed = {**legacy, "teacher": {"changed": True}}
        (self.root / "state.json").write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_GENERATION_COLLISION"):
            persist(self.root, successor)
        self.assertEqual(read_current(self.root), changed)

    def test_persist_materializes_missing_generation_pointer_without_new_node(self):
        receipt = self.receipt()
        (self.root / "state.json").write_text(json.dumps(receipt))
        migrate_current_head(self.root, receipt)
        head_before = (self.root / "state.json").read_bytes()
        self.assertFalse((self.root / "states/0000007.json").exists())
        from bilqis_mlx.data_plane import data_plane
        nodes_before = data_plane().stats()["nodes"]

        self.assertEqual(persist(self.root, receipt), receipt)
        self.assertEqual((self.root / "state.json").read_bytes(), head_before)
        self.assertEqual((self.root / "states/0000007.json").read_bytes(),
                         head_before)
        self.assertEqual(read_generation(self.root, 7), receipt)
        self.assertEqual(data_plane().stats()["nodes"], nodes_before)

    def test_persist_identical_generation_retry_does_not_reparent(self):
        first = self.receipt()
        (self.root / "state.json").write_text(json.dumps(first))
        migrate_current_head(self.root, first)
        successor = self.receipt(8)
        self.assertEqual(persist(self.root, successor), successor)
        head_before = (self.root / "state.json").read_bytes()
        generation_before = (self.root / "states/0000008.json").read_bytes()
        from bilqis_mlx.data_plane import data_plane
        nodes_before = data_plane().stats()["nodes"]

        self.assertEqual(persist(self.root, json.loads(json.dumps(successor))), successor)
        self.assertEqual((self.root / "state.json").read_bytes(), head_before)
        self.assertEqual((self.root / "states/0000008.json").read_bytes(),
                         generation_before)
        self.assertEqual(data_plane().stats()["nodes"], nodes_before)

    def test_persist_changed_or_stale_generation_never_rewinds_head(self):
        first = self.receipt()
        (self.root / "state.json").write_text(json.dumps(first))
        migrate_current_head(self.root, first)
        second = self.receipt(8)
        persist(self.root, second)
        head_eight = (self.root / "state.json").read_bytes()
        changed = self.receipt(8)
        changed["school"] = {"grade": "C", "queue": ["C.NUMBER"]}
        with self.assertRaisesRegex(ValueError, "STATE_DAG_IMMUTABLE_GENERATION_COLLISION"):
            persist(self.root, changed)
        self.assertEqual((self.root / "state.json").read_bytes(), head_eight)

        third = self.receipt(9)
        third["school"] = {"grade": "C", "queue": ["C.NUMBER"]}
        persist(self.root, third)
        head_nine = (self.root / "state.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "STATE_DAG_IMMUTABLE_GENERATION_COLLISION"):
            persist(self.root, second)
        self.assertEqual((self.root / "state.json").read_bytes(), head_nine)
        self.assertEqual(read_current(self.root), third)

    def test_persist_replays_existing_orphan_generation_without_new_node(self):
        first = self.receipt()
        (self.root / "state.json").write_text(json.dumps(first))
        migrate_current_head(self.root, first)
        first_head = (self.root / "state.json").read_bytes()
        second = self.receipt(8)
        persist(self.root, second)
        second_head = (self.root / "state.json").read_bytes()
        from bilqis_mlx.data_plane import data_plane
        nodes_before = data_plane().stats()["nodes"]

        (self.root / "state.json").write_bytes(first_head)
        self.assertEqual(persist(self.root, second), second)
        self.assertEqual((self.root / "state.json").read_bytes(), second_head)
        self.assertEqual(read_current(self.root), second)
        self.assertEqual(data_plane().stats()["nodes"], nodes_before)
