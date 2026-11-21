"""Issue #304 semantic release/materialization currentness projection."""
from __future__ import annotations

from types import SimpleNamespace
from types import ModuleType
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.native_contracts import (
    AuthenticatedGeneration, NativeProjectionMaterial, invalid,
)
from bilqis_mlx.control_plane.native_source import native_query_source
from bilqis_mlx.control_plane.projection.semantic_release import (
    _projection_record, _release_record, accepted_semantic_release_records,
)
from bilqis_mlx.mission_control import SemanticProjectionState, ValueState
from bilqis_mlx.runtime.akasha_outbox import AkashaEvent, AkashaEventKind


DIGESTS = {letter: letter * 64 for letter in "123456789abcdef"}


def generation() -> AuthenticatedGeneration:
    return AuthenticatedGeneration(
        manifest_sha256=DIGESTS["1"],
        acceptance_sha256=DIGESTS["2"],
        manifest={
            "run_id": "run-semantic",
            "generation": 7,
            "provenance": {"release_digest": DIGESTS["3"]},
            "topology": {"digest": DIGESTS["4"]},
        },
        acceptance={
            "candidate_identity_sha256": DIGESTS["5"],
            "factory_release_sha256": DIGESTS["6"],
        },
        run_identity={"run_identity_sha256": DIGESTS["7"]},
        correction_frontier={}, teacher_state={}, outbox=(),
    )


def snapshot():
    return SimpleNamespace(
        bundle_id=DIGESTS["8"], release_sha256=DIGESTS["3"],
        source_bundle_id=DIGESTS["9"], canonical_rdf_sha256=DIGESTS["a"],
        coverage_sha256=DIGESTS["b"], conformance_sha256=DIGESTS["c"],
        source_rows_sha256=DIGESTS["d"], active_set_sha256=DIGESTS["e"],
        counts=SimpleNamespace(
            source_rows=977, semantic_concepts=801, active_abi_indices=742,
            source_held=11, source_ir_only=13,
            implementation_uncovered=17,
        ),
    )


def materialization(*, rdf=DIGESTS["a"], coverage=DIGESTS["b"],
                    coverage_status="complete", recorded_at=100):
    payload = {
        "graph": "semantic",
        "owner": "semantic-release-authority",
        "canonical_rdf_sha256": rdf,
        "materialization_receipt_sha256": DIGESTS["f"],
        "projection_version": "1.0.0",
        "coverage_status": coverage_status,
        "semantic_coverage_sha256": coverage,
        "importer_implementation_sha256": DIGESTS["1"],
        "smoke_suite_sha256": DIGESTS["2"],
    }
    return AkashaEvent.from_payload(
        kind=AkashaEventKind.MATERIALIZATION,
        subject_id="semantic-materialization:semantic-release-authority:semantic",
        source_receipt_sha256=DIGESTS["f"], payload=payload,
        source_time=recorded_at, effective_time=recorded_at,
        observed_at=recorded_at, recorded_at=recorded_at,
    )


class SemanticReleaseProjectionTests(unittest.TestCase):
    def test_release_preserves_exact_authenticated_identity_and_unknown_debt_verdict(self):
        record = _release_record(generation(), snapshot())
        self.assertEqual(record.semantic_release_sha256, DIGESTS["3"])
        self.assertEqual(record.canonical_rdf_sha256, DIGESTS["a"])
        self.assertEqual(record.coverage_sha256, DIGESTS["b"])
        self.assertEqual(record.active_set_sha256, DIGESTS["e"])
        self.assertEqual(record.conformance_status, "COMPLETE")
        self.assertEqual(record.source_rows, 977)
        self.assertEqual(record.active_abi_indices, 742)
        self.assertEqual(record.source_held, 11)
        self.assertEqual(record.source_ir_only, 13)
        self.assertEqual(record.implementation_uncovered, 17)
        self.assertIs(record.frontier_debt.state, ValueState.MISSING)
        self.assertIs(record.coverage_status.state, ValueState.MISSING)

    def test_exact_materialization_is_current(self):
        record = _projection_record(generation(), snapshot(), (materialization(),))
        self.assertIs(record.state, SemanticProjectionState.CURRENT)
        self.assertEqual(record.canonical_rdf_sha256.value, DIGESTS["a"])
        self.assertEqual(record.semantic_coverage_sha256.value, DIGESTS["b"])

    def test_exact_materialization_with_partial_coverage_is_partial(self):
        record = _projection_record(
            generation(), snapshot(), (materialization(coverage_status="partial"),))
        self.assertIs(record.state, SemanticProjectionState.PARTIAL)

    def test_mismatched_materialization_is_stale(self):
        record = _projection_record(
            generation(), snapshot(),
            (materialization(rdf=DIGESTS["c"], coverage=DIGESTS["d"]),),
        )
        self.assertIs(record.state, SemanticProjectionState.STALE)

    def test_no_materialization_is_machine_readable_missing(self):
        record = _projection_record(generation(), snapshot(), ())
        self.assertIs(record.state, SemanticProjectionState.MISSING)
        self.assertIs(record.materialization_receipt_sha256.state, ValueState.MISSING)

    def test_matching_receipt_wins_over_newer_unrelated_projection(self):
        current = materialization(recorded_at=100)
        unrelated = materialization(
            rdf=DIGESTS["c"], coverage=DIGESTS["d"], recorded_at=200)
        record = _projection_record(generation(), snapshot(), (current, unrelated))
        self.assertIs(record.state, SemanticProjectionState.CURRENT)
        self.assertEqual(record.meta.materialized_at, 100)

    def test_native_query_cache_rebuilds_for_outbox_change_but_not_trainer_only_change(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bamf-state.json").write_text("{}", encoding="utf-8")
            trainer = root / "trainer-observed.json"
            outbox = root / "akasha-outbox.sqlite3"
            trainer.write_text("one", encoding="utf-8")
            outbox.write_text("one", encoding="utf-8")
            material = NativeProjectionMaterial((), (), (), {})
            with (
                patch("bilqis_mlx.control_plane.native_source.materialize_native_projection",
                      return_value=material) as materialize,
                patch("bilqis_mlx.control_plane.native_source._run_refs",
                      return_value=("run-ref",)),
                patch("bilqis_mlx.control_plane.native_source.observed_records",
                      return_value=()),
            ):
                source = native_query_source(root)
                source()
                source()
                self.assertEqual(materialize.call_count, 1)
                trainer.write_text("trainer changed", encoding="utf-8")
                source()
                self.assertEqual(materialize.call_count, 1)
                outbox.write_text("materialization changed", encoding="utf-8")
                source()
                self.assertEqual(materialize.call_count, 2)

    def test_missing_feature_authority_degrades_only_semantic_cockpit(self):
        bamf_bundle = ModuleType("bilqis_mlx.runtime.bamf_bundle")
        bamf_bundle.read_accepted_generation_semantic_snapshot = (
            lambda _path: invalid("SEMANTIC_FIXTURE_UNAVAILABLE"))
        with TemporaryDirectory() as temporary:
            with patch.dict(sys.modules, {"bilqis_mlx.runtime.bamf_bundle": bamf_bundle}):
                records = accepted_semantic_release_records(Path(temporary), generation())
        self.assertEqual(len(records), 1)
        self.assertIs(records[0].state, SemanticProjectionState.ERROR)


if __name__ == "__main__":
    unittest.main()
