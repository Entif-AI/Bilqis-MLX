from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.autonomy import (
    EvidenceKind,
    EvidenceReceipt,
    initial_evidence_ledger,
    evidence_complete_capabilities,
    next_work,
    obligations_for_capability,
    record_evidence,
)
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class AutonomousCurriculumPlannerTests(unittest.TestCase):
    def setUp(self):
        names = ("A.BASE", "A.OTHER", "A.COMPOSITE", "A.F3", "A.F4", "A.F5")
        caps = []
        for name in names:
            prerequisites = (("A.BASE", "A.OTHER") if name == "A.COMPOSITE" else ())
            caps.append(Capability(
                id=name, difficulty="fixture", source_anchor="repo:fixture/autonomy",
                taught_roots=("fixture." + name.lower(),),
                examined_roots=("fixture." + name.lower(),),
                prerequisites=prerequisites, composed_of=prerequisites,
                answer_families=(AnswerFamily("binary", BINARY),),
                lesson_generator="fixture.autonomy-generator/v1",
                independent_oracle="fixture.autonomy-oracle/v1",
            ))
        grade = Grade(
            "A", tuple(caps), assessment_sha256="a" * 64,
            exam_item_counts=tuple((name, 4) for name in names),
            teaching_stages=(("A.BASE", "A.OTHER"),
                             ("A.COMPOSITE", "A.F3", "A.F4", "A.F5")),
        )
        course = Course((grade,), "fixture.autonomy/v1", "b" * 64, "a" * 64)
        descriptor = SourceAdapter(
            "fixture.autonomy-adapter/v1", "fixture.autonomy-generator/v1",
            ("fixture.autonomy-oracle/v1",), "d" * 64,
            teaching_option_ids=("fixture.transfer",),
        )
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            descriptor, lambda **_: (), lambda row, **_: True),))
        self.release = compile_factory_release(course, registry)
        self.receipt_index = 0

    def receipt(self, obligation, passed=True, specimen_count=None):
        self.receipt_index += 1
        count = obligation.minimum_specimens if specimen_count is None else specimen_count
        return EvidenceReceipt(
            obligation_id=obligation.obligation_id,
            evidence_id=f"evidence-{self.receipt_index}",
            checkpoint_sha256="e" * 64,
            optimizer_step=self.receipt_index,
            cohort_sha256=_sha(f"cohort-{self.receipt_index}"),
            specimen_count=count,
            passed=passed,
        )

    def close_current_capability(self, ledger):
        capability = next_work(self.release, ledger).capability_id
        while True:
            work = next_work(self.release, ledger)
            if work is None or work.capability_id != capability:
                return ledger
            ledger = record_evidence(self.release, ledger, self.receipt(work.obligation))

    def test_generation_axes_constrain_evidence_without_becoming_mastery_claims(self):
        obligations = obligations_for_capability(self.release, "A.BASE")
        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations[0].kind, EvidenceKind.DIRECT)
        self.assertEqual(obligations[0].generation_axes,
                         ("source-valid", "balanced-gold", "fresh-seed"))

    def test_planner_closes_roots_then_unlocks_composite(self):
        ledger = initial_evidence_ledger(self.release)
        first = next_work(self.release, ledger)
        self.assertEqual(first.capability_id, "A.BASE")
        self.assertEqual(first.obligation.kind, EvidenceKind.DIRECT)
        self.assertEqual(first.teaching_option_ids,
                         ("source.direct/A.BASE", "fixture.transfer"))

        ledger = self.close_current_capability(ledger)
        self.assertEqual(evidence_complete_capabilities(self.release, ledger), ("A.BASE",))
        self.assertEqual(next_work(self.release, ledger).capability_id, "A.OTHER")

        ledger = self.close_current_capability(ledger)
        self.assertEqual(evidence_complete_capabilities(self.release, ledger),
                         ("A.BASE", "A.OTHER"))
        work = next_work(self.release, ledger)
        self.assertEqual(work.capability_id, "A.COMPOSITE")
        kinds = {item.kind for item in obligations_for_capability(
            self.release, "A.COMPOSITE")}
        self.assertEqual(kinds, {EvidenceKind.DIRECT, EvidenceKind.PREREQUISITE,
                                 EvidenceKind.COMPOSITION})

    def test_next_work_is_deterministic_for_unchanged_ledger(self):
        ledger = initial_evidence_ledger(self.release)
        first = next_work(self.release, ledger)
        second = next_work(self.release, ledger)
        self.assertEqual(first, second)

    def test_composition_evidence_is_required_for_evidence_complete_state(self):
        ledger = initial_evidence_ledger(self.release)
        ledger = self.close_current_capability(ledger)
        ledger = self.close_current_capability(ledger)
        composite = obligations_for_capability(self.release, "A.COMPOSITE")
        missing = next(item for item in composite if item.kind is EvidenceKind.COMPOSITION)
        for obligation in composite:
            if obligation != missing:
                ledger = record_evidence(self.release, ledger, self.receipt(obligation))
        self.assertNotIn("A.COMPOSITE", evidence_complete_capabilities(self.release, ledger))
        self.assertEqual(next_work(self.release, ledger).obligation, missing)
        ledger = record_evidence(self.release, ledger, self.receipt(missing))
        self.assertIn("A.COMPOSITE", evidence_complete_capabilities(self.release, ledger))

    def test_failed_receipt_reopens_before_new_work(self):
        ledger = initial_evidence_ledger(self.release)
        obligation = next_work(self.release, ledger).obligation
        ledger = record_evidence(self.release, ledger, self.receipt(obligation))
        self.assertNotEqual(next_work(self.release, ledger).obligation.obligation_id,
                            obligation.obligation_id)
        ledger = record_evidence(self.release, ledger, self.receipt(obligation, passed=False))
        self.assertEqual(next_work(self.release, ledger).obligation.obligation_id,
                         obligation.obligation_id)
        self.assertNotIn("A.BASE", evidence_complete_capabilities(self.release, ledger))

    def test_passing_receipt_must_meet_obligation_specimen_floor(self):
        ledger = initial_evidence_ledger(self.release)
        obligation = next_work(self.release, ledger).obligation
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_EVIDENCE_SPECIMENS"):
            record_evidence(self.release, ledger,
                            self.receipt(obligation, specimen_count=obligation.minimum_specimens - 1))

    def test_evidence_is_bound_to_exact_factory_release(self):
        ledger = initial_evidence_ledger(self.release)
        changed = replace(self.release, release_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "AUTONOMY_RELEASE_MISMATCH"):
            next_work(changed, ledger)

    def test_autonomous_loop_finishes_without_grade_specific_dispatch(self):
        ledger = initial_evidence_ledger(self.release)
        seen = []
        for _ in range(40):
            work = next_work(self.release, ledger)
            if work is None:
                break
            seen.append((work.capability_id, work.obligation.kind))
            ledger = record_evidence(self.release, ledger, self.receipt(work.obligation))
        else:
            self.fail("autonomous evidence loop did not converge")

        self.assertLess(seen.index(("A.BASE", EvidenceKind.DIRECT)),
                        seen.index(("A.COMPOSITE", EvidenceKind.DIRECT)))
        self.assertLess(seen.index(("A.OTHER", EvidenceKind.DIRECT)),
                        seen.index(("A.COMPOSITE", EvidenceKind.DIRECT)))
        self.assertEqual(evidence_complete_capabilities(self.release, ledger),
                         tuple(item.capability_id for item in self.release.capabilities))
        self.assertIsNone(next_work(self.release, ledger))


if __name__ == "__main__":
    unittest.main()
