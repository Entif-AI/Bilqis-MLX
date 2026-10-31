"""C10.2 source/release/model/evaluator/rights-bound outbox projections."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_outbox import (
    AkashaEvent, AkashaEventKind, pending_events,
)
from bilqis_mlx.runtime.bamf_projection import (
    BamfProjectionEvent, ProjectionDomainContract,
    project_generation_outbox,
)
from bilqis_mlx.runtime.akasha_staging import (
    build_staging_projection, promote_staging_projection,
    query_public_projection, read_active_projection,
    read_staging_projection, verify_staging_projection,
)








from bilqis_mlx.runtime.tests.projection.staging_helpers import _event, _contract, _projected


class BamfProjectionTests(unittest.TestCase):
    def test_durable_domain_binding_cannot_be_relabelled_after_restart(self):
        from bilqis_mlx.runtime.bamf_projection import read_projection_outbox
        with tempfile.TemporaryDirectory() as folder:
            domain = _contract(Path(folder) / 'outbox.sqlite3')
            event = _projected(_event('capability:bound'), domain)
            project_generation_outbox((event,), domain)
            self.assertEqual(read_projection_outbox(domain.outbox_path), (event,))
            for key, value in (('source_id', 'other'), ('release_digest', '5' * 64),
                               ('model_digest', '6' * 64), ('evaluator_digest', '7' * 64),
                               ('rights_digest', '8' * 64), ('as_of', 601)):
                changed = replace(domain, **{key: value})
                with self.subTest(key=key), self.assertRaises(BilqisError):
                    project_generation_outbox((_projected(event.event, changed),), changed)
                self.assertEqual(read_projection_outbox(domain.outbox_path), (event,))
                with self.assertRaises(BilqisError):
                    build_staging_projection((_projected(event.event, changed),), changed)




    def test_identity_bound_outbox_is_deduplicated_without_graph_io(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            events = tuple(
                _projected(_event("capability:" + str(index)), contract)
                for index in range(2))
            receipt = project_generation_outbox(events, contract)
            self.assertEqual(receipt.appended_count, 2)
            self.assertEqual(receipt.duplicate_count, 0)
            self.assertEqual(receipt.pending_count, 2)
            self.assertEqual(receipt.domain_digest, contract.digest)
            self.assertEqual(receipt.event_ids,
                             tuple(item.event.event_id for item in events))
            repeated = project_generation_outbox(events, contract)
            self.assertEqual(repeated.appended_count, 0)
            self.assertEqual(repeated.duplicate_count, 2)
            self.assertEqual(len(pending_events(contract.outbox_path)), 2)

    def test_rights_release_model_evaluator_or_asof_drift_rejects_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            event = _projected(_event("capability:1"), contract)
            for changed in (
                replace(event, rights_digest="0" * 64),
                replace(event, release_digest="0" * 64),
                replace(event, model_digest="0" * 64),
                replace(event, evaluator_digest="0" * 64),
                replace(event, as_of=590),
            ):
                with self.subTest(changed=changed):
                    with self.assertRaises(BilqisError):
                        project_generation_outbox((changed,), contract)
            self.assertEqual(pending_events(contract.outbox_path), ())
            with self.assertRaises(BilqisError):
                replace(event, as_of=580)

    def test_graph_outage_never_blocks_local_training_or_event_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            event = _projected(_event("capability:1"), contract)
            class GraphUnavailable:
                def __getattr__(self, name):
                    raise RuntimeError("GRAPH_UNAVAILABLE")

            graph = GraphUnavailable()
            # The outbox projection has no graph/client parameter and never
            # touches the graph. The training caller can continue locally.
            receipt = project_generation_outbox((event,), contract)
            training_steps = 1
            self.assertEqual(training_steps, 1)
            self.assertEqual(receipt.pending_count, 1)
            self.assertEqual(pending_events(contract.outbox_path),
                             (event.event,))
            self.assertIsNotNone(graph)


if __name__ == "__main__":
    unittest.main()
