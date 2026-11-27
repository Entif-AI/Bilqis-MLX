"""Verify that a relocated diagnostic cannot invent or silently change cadence."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
from tempfile import TemporaryDirectory
import unittest

from scripts.bamf.profiling.issue1645.dynamics.cadence_custody import (
    KEY, SCHEMA, verified_projection,
)
from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import isolated_copy
from scripts.bamf.profiling.issue1645.dynamics.artifacts import sha256_file


class CadenceCustody(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.frozen = self.root / "frozen" / "run"
        self.frozen.mkdir(parents=True)
        self.target = self.root / "target"
        self.target.mkdir()
        self.plane = self.frozen.parent / "plane.sqlite3"
        pointer = {"run_id": "run", "generation": 6,
                   "manifest_sha256": "a" * 64, "acceptance_sha256": "b" * 64}
        payload = {"schema": SCHEMA, "run_id": "run", "accepted_generation": 6,
                   "accepted_manifest_sha256": "a" * 64,
                   "accepted_acceptance_sha256": "b" * 64,
                   "attempts": [], "seen_accepted_events": []}
        event = {"event": "BAMF_GENERATION_ACCEPTED", "event_id": "c" * 64}
        canonical = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
        self.line = canonical + b"\n"
        self.frontier = len(self.line)
        for run in (self.frozen, self.target):
            (run / "bamf-state.json").write_text(json.dumps(pointer))
            (run / "events.jsonl").write_bytes(self.line)
        (self.target / "events.jsonl").write_bytes(self.line + b'{}\n')
        self.projection = self.root / "projection.json"
        self.projection.write_text(json.dumps({"indexed_bytes": self.frontier,
                                              "payload": payload}))
        with sqlite3.connect(self.plane) as db:
            db.executescript("""
                CREATE TABLE event_projections(run_dir,projection_key,schema_version,
                    st_dev,st_ino,indexed_bytes,payload);
                CREATE TABLE event_ledgers(run_dir,st_dev,st_ino,indexed_bytes);
                CREATE TABLE event_stream(run_dir,sequence,start_byte,end_byte,
                    event_id,payload_sha256,payload);
            """)
            db.execute("INSERT INTO event_projections VALUES(?,?,?,?,?,?,?)",
                       ("original", KEY, SCHEMA, 1, 2, self.frontier, json.dumps(payload)))
            db.execute("INSERT INTO event_ledgers VALUES(?,?,?,?)",
                       ("original", 1, 2, self.frontier))
            db.execute("INSERT INTO event_stream VALUES(?,?,?,?,?,?,?)",
                       ("original", 1, 0, self.frontier, event["event_id"],
                        sha256(canonical).hexdigest(), canonical))

        (self.root / "receipt.json").write_text('{"source_mutated": false}')
        self.pin = self.root / "freeze-manifest.json"
        self.expected = self.freeze_pin()

    def freeze_pin(self):
        self.pin.write_text(json.dumps({
            "schema": "bilqis.research.cadence-freeze/v1",
            "origin_receipt_sha256": sha256_file(self.root / "receipt.json"),
            "projection_sha256": sha256_file(self.projection),
            "pointer_sha256": sha256_file(self.frozen / "bamf-state.json"),
            "prefix_sha256": sha256_file(self.frozen / "events.jsonl"),
            "plane_sha256": sha256_file(self.plane),
            "indexed_bytes": self.frontier, "indexed_records": 1,
        }))
        return sha256_file(self.pin)

    def verify(self, *, repin=False):
        return verified_projection(self.root, self.target, self.pin,
                                   self.freeze_pin() if repin else self.expected)

    def test_exact_prefix_and_index_are_required(self):
        _, receipt = self.verify()
        self.assertEqual(receipt["unique_lines"], 1)
        self.assertEqual(receipt["prefix_sha256"], sha256(self.line).hexdigest())
        self.assertEqual(receipt["indexed_bytes"], self.frontier)
        self.assertEqual((self.target / "events.jsonl").read_bytes(), self.line + b'{}\n')

    def test_projection_from_a_different_accepted_parent_is_rejected(self):
        pointer = json.loads((self.target / "bamf-state.json").read_text())
        pointer["generation"] += 1
        pointer["manifest_sha256"] = "d" * 64
        (self.target / "bamf-state.json").write_text(json.dumps(pointer))
        with self.assertRaisesRegex(ValueError, "projection parent pointer mismatch"):
            self.verify()

    def test_changed_ledger_prefix_is_rejected(self):
        (self.target / "events.jsonl").write_bytes(self.line.replace(b'ACCEPTED', b'REJECTED'))
        with self.assertRaisesRegex(ValueError, "target ledger prefix mismatch"):
            self.verify()

    def test_caller_authored_projection_is_rejected(self):
        data = json.loads(self.projection.read_text())
        data["payload"]["attempts"].append(["fabricated"])
        self.projection.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "artifact digest mismatch"):
            self.verify()

    def test_index_gap_is_rejected(self):
        with sqlite3.connect(self.plane) as db:
            db.execute("DELETE FROM event_stream")
        with self.assertRaisesRegex(ValueError, "incomplete indexed ledger frontier"):
            self.verify(repin=True)

    def test_index_payload_drift_is_rejected(self):
        with sqlite3.connect(self.plane) as db:
            db.execute("UPDATE event_stream SET payload=?", (b"{}",))
        with self.assertRaisesRegex(ValueError, "indexed ledger payload mismatch"):
            self.verify(repin=True)

    def test_missing_external_pin_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "independently pinned"):
            verified_projection(self.root, self.target)

    def test_matching_fabricated_projection_and_db_cannot_replace_pin(self):
        data = json.loads(self.projection.read_text())
        data["payload"]["attempts"].append(["fabricated"])
        self.projection.write_text(json.dumps(data))
        with sqlite3.connect(self.plane) as db:
            db.execute("UPDATE event_projections SET payload=?", (json.dumps(data["payload"]),))
        self.freeze_pin()  # A caller-generated matching manifest does not replace the external pin.
        with self.assertRaisesRegex(ValueError, "artifact digest mismatch"):
            self.verify()

    def test_duplicate_index_range_rejected_even_when_pinned(self):
        with sqlite3.connect(self.plane) as db:
            db.execute("INSERT INTO event_stream SELECT run_dir,2,start_byte,end_byte,event_id,"
                       "payload_sha256,payload FROM event_stream WHERE sequence=1")
        with self.assertRaisesRegex(ValueError, "duplicate or incomplete"):
            self.verify(repin=True)

    def test_index_sequence_gap_rejected_even_when_pinned(self):
        with sqlite3.connect(self.plane) as db:
            db.execute("UPDATE event_stream SET sequence=2")
        with self.assertRaisesRegex(ValueError, "noncontiguous index sequence"):
            self.verify(repin=True)

    def test_unpinned_wal_rejected(self):
        Path(str(self.plane) + "-wal").write_bytes(b"unexpected bytes")
        with self.assertRaisesRegex(ValueError, "unpinned WAL"):
            self.verify()

    def test_symbolic_link_is_rejected_before_clone(self):
        (self.target / "link").symlink_to(self.frozen)
        destination = self.root / "disposable"
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            isolated_copy(self.target, self.plane, destination)
        self.assertFalse(destination.exists())

    def test_controlled_cli_rejects_symlink_before_resolving(self):
        from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import main
        alias = self.root / "alias"
        alias.symlink_to(self.target, target_is_directory=True)
        destination = self.root / "disposable"
        with patch("sys.argv", ["authentic_dynamics", str(alias), str(self.plane), str(destination)]):
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                main()
        self.assertFalse(destination.exists())

    def test_symlink_ancestor_and_dangling_destination_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.frozen.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            isolated_copy(alias / "run", self.plane, self.root / "disposable")
        destination = self.root / "dangling"
        destination.symlink_to(self.root / "uncreated", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            isolated_copy(self.target, self.plane, destination)
        self.assertFalse((self.root / "uncreated").exists())

    def test_native_cli_rejects_symlink_before_admission(self):
        from scripts.bamf.profiling.issue1645.dynamics.native_lesson_dynamics import main
        alias = self.root / "alias"
        alias.symlink_to(self.target, target_is_directory=True)
        destination = self.root / "disposable"
        argv = ["native_lesson_dynamics", str(alias), str(self.plane), str(destination),
                "--protected", str(self.root), "--protected-result-sha256", "0" * 64]
        with patch("sys.argv", argv):
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                main()
        self.assertFalse(destination.exists())
