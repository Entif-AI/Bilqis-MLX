"""Verify that a relocated diagnostic cannot invent or silently change cadence."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.bamf.profiling.issue1645.dynamics.cadence_custody import (
    KEY, SCHEMA, verified_projection,
)
from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import isolated_copy


class CadenceCustody(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
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

    def test_exact_prefix_and_index_are_required(self):
        _, receipt = verified_projection(self.root, self.target)
        self.assertEqual(receipt["unique_lines"], 1)
        self.assertEqual(receipt["prefix_sha256"], sha256(self.line).hexdigest())
        self.assertEqual(receipt["indexed_bytes"], self.frontier)
        self.assertEqual((self.target / "events.jsonl").read_bytes(), self.line + b'{}\n')

    def test_changed_ledger_prefix_is_rejected(self):
        (self.target / "events.jsonl").write_bytes(self.line.replace(b'ACCEPTED', b'REJECTED'))
        with self.assertRaisesRegex(ValueError, "target ledger prefix mismatch"):
            verified_projection(self.root, self.target)

    def test_caller_authored_projection_is_rejected(self):
        data = json.loads(self.projection.read_text())
        data["payload"]["attempts"].append(["fabricated"])
        self.projection.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "projection authority"):
            verified_projection(self.root, self.target)

    def test_index_gap_is_rejected(self):
        with sqlite3.connect(self.plane) as db:
            db.execute("DELETE FROM event_stream")
        with self.assertRaisesRegex(ValueError, "incomplete indexed ledger frontier"):
            verified_projection(self.root, self.target)

    def test_index_payload_drift_is_rejected(self):
        with sqlite3.connect(self.plane) as db:
            db.execute("UPDATE event_stream SET payload=?", (b"{}",))
        with self.assertRaisesRegex(ValueError, "indexed ledger payload mismatch"):
            verified_projection(self.root, self.target)

    def test_symbolic_link_is_rejected_before_clone(self):
        (self.target / "link").symlink_to(self.frozen)
        destination = self.root / "disposable"
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            isolated_copy(self.target, self.plane, destination)
        self.assertFalse(destination.exists())
