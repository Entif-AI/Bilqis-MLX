from dataclasses import replace
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.autonomy import EvidenceKind, EvidenceObligation
from bilqis_mlx.factory.evidence import draw_evidence_rows, measure_evidence
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release


def rows(*, capability, seed, each, **_):
    return tuple({
        "id": f"{capability}:{seed}:{i}", "source_id": f"{capability}:{seed}:{i}",
        "capability": capability, "gold": "TRUE" if i % 2 else "FALSE",
        "answer_kind": "binary", "producer": "A.BASE" if i % 3 == 0 else "A.OTHER",
        "slot": i % 2,
    } for i in range(each))


def check(row, **_):
    return row["gold"] in ("TRUE", "FALSE")


def witness(row, obligation, **_):
    if obligation.kind is EvidenceKind.PREREQUISITE:
        return row["producer"] == obligation.key
    if obligation.kind is EvidenceKind.COMPOSITION:
        producer, slot = obligation.key.split("@")
        return row["producer"] == producer and row["slot"] == int(slot)
    return True


class EvidenceExecutionTests(unittest.TestCase):
    def setUp(self):
        caps = tuple(Capability(
            id=f"A.C{i}", difficulty="fixture", source_anchor="repo:fixture/evidence",
            taught_roots=(f"fixture.{i}",), examined_roots=(f"fixture.{i}",),
            prerequisites=(), composed_of=(),
            answer_families=(AnswerFamily("binary", BINARY),),
            lesson_generator="fixture.evidence/v1", independent_oracle="fixture.oracle/v1",
        ) for i in range(6))
        grade = Grade("A", caps, assessment_sha256="a" * 64,
                      exam_item_counts=tuple((cap.id, 4) for cap in caps))
        course = Course((grade,), "fixture.evidence/v1", "b" * 64, "a" * 64)
        descriptor = SourceAdapter(
            "fixture.evidence-adapter/v1", "fixture.evidence/v1",
            ("fixture.oracle/v1",), "d" * 64)
        self.registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            descriptor, rows, check, witness=witness),))
        self.release = compile_factory_release(course, self.registry)
        self.checkpoint = {
            "sha256": "e" * 64, "optimizer_step": 17,
            "model_and_native_adamw": True,
        }

    def obligation(self, kind=EvidenceKind.DIRECT, key="source.direct", minimum=4):
        return EvidenceObligation(
            obligation_id=f"A.C0/{kind.value.lower()}/{key}", capability_id="A.C0",
            kind=kind, key=key, minimum_specimens=minimum,
            generation_axes=("source-valid", "fresh-seed"),
            requires_capabilities=(() if kind is EvidenceKind.DIRECT else ("A.BASE",)),
        )

    def test_direct_evidence_uses_fresh_source_checked_rows(self):
        obligation = self.obligation()
        selected = draw_evidence_rows(
            None, {}, self.release, self.registry, obligation, seed=23)
        self.assertEqual(len(selected), 4)
        self.assertEqual({row["capability"] for row in selected}, {"A.C0"})

    def test_composition_evidence_filters_for_exact_adapter_witness(self):
        obligation = self.obligation(EvidenceKind.COMPOSITION, "A.BASE@0", minimum=2)
        selected = draw_evidence_rows(
            None, {}, self.release, self.registry, obligation, seed=23)
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(row["producer"] == "A.BASE" and row["slot"] == 0
                            for row in selected))

    def test_measurement_returns_receipt_bound_to_checkpoint_and_cohort(self):
        obligation = self.obligation()
        receipt = measure_evidence(
            None, {}, self.release, self.registry, obligation,
            checkpoint=self.checkpoint, seed=23,
            predictor=lambda batch: {row["id"]: row["gold"] for row in batch},
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.checkpoint_sha256, self.checkpoint["sha256"])
        self.assertEqual(receipt.optimizer_step, 17)
        self.assertEqual(receipt.specimen_count, 4)
        self.assertEqual(len(receipt.cohort_sha256), 64)

    def test_failed_predictions_return_failed_receipt_without_mutating_model(self):
        obligation = self.obligation()
        receipt = measure_evidence(
            None, {}, self.release, self.registry, obligation,
            checkpoint=self.checkpoint, seed=23,
            predictor=lambda batch: {row["id"]: "FALSE" for row in batch},
        )
        self.assertFalse(receipt.passed)
        self.assertEqual(self.checkpoint["optimizer_step"], 17)

    def test_non_direct_obligation_fails_closed_without_adapter_witness(self):
        plain = SourceAdapterRegistry((RegisteredSourceAdapter(
            self.release.source_adapters[0], rows, check),))
        obligation = self.obligation(EvidenceKind.COMPOSITION, "A.BASE@0", minimum=1)
        with self.assertRaisesRegex(ValueError, "EVIDENCE_WITNESS_ADAPTER_REQUIRED"):
            draw_evidence_rows(None, {}, self.release, plain, obligation, seed=23)


if __name__ == "__main__":
    unittest.main()
