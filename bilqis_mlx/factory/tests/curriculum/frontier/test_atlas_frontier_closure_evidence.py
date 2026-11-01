"""A09.2 prerequisite evidence and implementation-debt behavior."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_closure import (
    ClosureStatus,
    PrerequisiteCapabilityBinding,
)
from bilqis_mlx.factory.skos_curriculum import IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import (
    current_evidence,
    rehash,
    resolve,
    three_node_snapshot,
)


class AtlasFrontierClosureEvidenceTests(unittest.TestCase):
    def test_true_dependency_blocks_but_unrelated_ready_work_survives(self):
        closure = resolve(three_node_snapshot())
        by_id = {(item.semantic_id, item.family_id): item for item in closure.candidates}
        self.assertEqual(
            by_id[("urn:one", "positive_identity")].status,
            ClosureStatus.IMPLEMENTATION_UNCOVERED,
        )
        blocked = by_id[("urn:two", "positive_identity")]
        self.assertEqual(blocked.status, ClosureStatus.IMPLEMENTATION_UNCOVERED)
        self.assertEqual(blocked.reasons[-1].dependency_id, "urn:one")
        self.assertEqual(
            by_id[("urn:three", "positive_identity")].status,
            ClosureStatus.READY,
        )
        self.assertLess(
            closure.constituent_order.index("urn:one"),
            closure.constituent_order.index("urn:two"),
        )

    def test_missing_typed_evidence_blocks_only_its_dependent_branch(self):
        base = three_node_snapshot()
        rows = tuple(replace(item, implementation_status=PROGRAM_BOUND)
                     for item in base.coverage_rows)
        snapshot = rehash(
            base,
            coverage_rows=rows,
            retained_mastery_debt=("cap.z",),
            retained_debt_source_sha256="d" * 64,
        )
        by_id = {item.semantic_id: item for item in resolve(snapshot).candidates}
        self.assertEqual(by_id["urn:one"].status, ClosureStatus.READY)
        self.assertEqual(by_id["urn:two"].status, ClosureStatus.WAITING_FOR_EVIDENCE)
        self.assertEqual(by_id["urn:three"].status, ClosureStatus.READY)

    def test_current_verified_evidence_unlocks_declared_dependency(self):
        base = three_node_snapshot()
        rows = tuple(replace(item, implementation_status=PROGRAM_BOUND)
                     for item in base.coverage_rows)
        release, ledger, plan, checkpoint, step = current_evidence("A.BASE")
        snapshot = rehash(
            base,
            coverage_rows=rows,
            admitted_factory_release_sha256=release.release_sha256,
            admission_receipt_sha256="7" * 64,
        )
        closure = resolve(
            snapshot,
            prerequisite_bindings=(
                PrerequisiteCapabilityBinding("urn:one", "A.BASE"),
            ),
            current_release=release,
            evidence_ledger=ledger,
            autonomy_plan=plan,
            checkpoint_sha256=checkpoint,
            optimizer_step=step,
        )
        self.assertTrue(all(
            item.status is ClosureStatus.READY for item in closure.candidates))

    def test_evidence_must_be_current_and_cannot_invent_mastery(self):
        base = three_node_snapshot()
        rows = tuple(replace(item, implementation_status=PROGRAM_BOUND)
                     for item in base.coverage_rows)
        release, ledger, plan, checkpoint, step = current_evidence("A.BASE")
        snapshot = rehash(
            base,
            coverage_rows=rows,
            admitted_factory_release_sha256=release.release_sha256,
            admission_receipt_sha256="7" * 64,
        )
        common = dict(
            current_release=release,
            evidence_ledger=ledger,
            autonomy_plan=plan,
            optimizer_step=step,
        )
        with self.assertRaises(BilqisError):
            resolve(
                snapshot,
                prerequisite_bindings=(
                    PrerequisiteCapabilityBinding("urn:one", "A.BASE"),
                ),
                checkpoint_sha256="6" * 64,
                **common,
            )
        with self.assertRaises(BilqisError):
            resolve(
                snapshot,
                prerequisite_bindings=(
                    PrerequisiteCapabilityBinding("urn:one", "cap:DOES_NOT_EXIST"),
                ),
                checkpoint_sha256=checkpoint,
                **common,
            )

    def test_binding_order_does_not_change_closure_identity(self):
        base = three_node_snapshot()
        rows = tuple(replace(item, implementation_status=PROGRAM_BOUND)
                     for item in base.coverage_rows)
        release, ledger, plan, checkpoint, step = current_evidence("A.BASE", "A.OTHER")
        snapshot = rehash(
            base,
            coverage_rows=rows,
            admitted_factory_release_sha256=release.release_sha256,
            admission_receipt_sha256="7" * 64,
        )
        bindings = (
            PrerequisiteCapabilityBinding("urn:one", "A.BASE"),
            PrerequisiteCapabilityBinding("urn:three", "A.OTHER"),
        )
        kwargs = dict(
            current_release=release,
            evidence_ledger=ledger,
            autonomy_plan=plan,
            checkpoint_sha256=checkpoint,
            optimizer_step=step,
        )
        first = resolve(snapshot, prerequisite_bindings=bindings, **kwargs)
        second = resolve(
            snapshot, prerequisite_bindings=tuple(reversed(bindings)), **kwargs)
        self.assertEqual(first, second)

    def test_implementation_debt_dominates_evidence_wait(self):
        base = three_node_snapshot()
        rows = tuple(
            replace(item, implementation_status=PROGRAM_BOUND)
            if item.semantic_id == "urn:one" else
            replace(item, implementation_status=IMPLEMENTATION_UNCOVERED)
            if item.semantic_id == "urn:two" else item
            for item in base.coverage_rows)
        snapshot = rehash(
            base,
            coverage_rows=rows,
            retained_mastery_debt=("cap.z",),
            retained_debt_source_sha256="d" * 64,
        )
        by_id = {item.semantic_id: item for item in resolve(snapshot).candidates}
        self.assertEqual(by_id["urn:one"].status, ClosureStatus.READY)
        self.assertEqual(by_id["urn:two"].status, ClosureStatus.IMPLEMENTATION_UNCOVERED)

    def test_semantic_capability_string_collision_is_not_mastery(self):
        base = three_node_snapshot()
        rows = tuple(replace(item, implementation_status=PROGRAM_BOUND)
                     for item in base.coverage_rows)
        snapshot = rehash(
            base,
            coverage_rows=rows,
            retained_mastery_debt=("urn:one",),
            retained_debt_source_sha256="d" * 64,
        )
        by_id = {item.semantic_id: item for item in resolve(snapshot).candidates}
        self.assertEqual(by_id["urn:one"].status, ClosureStatus.READY)
        self.assertEqual(by_id["urn:two"].status, ClosureStatus.WAITING_FOR_EVIDENCE)
