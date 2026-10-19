import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.autonomy import (
    EvidenceKind, EvidenceReceipt, compile_autonomy_plan,
    initial_evidence_ledger, next_work, record_evidence,
)
from bilqis_mlx.factory.development import (
    DevelopmentalStaircase, DevelopmentalTarget, RepresentationLayer,
    UnderstandingProjection,
)
from bilqis_mlx.factory.development_binding import (
    DevelopmentalBinding, bind_developmental_release,
)
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.understanding import (
    contract_for_target, plan_understanding_evidence,
)
import hashlib


def fixture():
    names = ("A.BASE", "A.OTHER", "A.STEP", "A.F3", "A.F4", "A.F5")
    caps = []
    for name in names:
        prerequisites = ("A.BASE", "A.OTHER") if name == "A.STEP" else ()
        caps.append(Capability(
            id=name, difficulty="fixture",
            source_anchor="repo:fixture/development-binding",
            taught_roots=("fixture." + name.lower(),),
            examined_roots=("fixture." + name.lower(),),
            prerequisites=prerequisites, composed_of=(),
            answer_families=(AnswerFamily("binary", BINARY),),
            lesson_generator="fixture.development/v1",
            independent_oracle="fixture.development-oracle/v1",
        ))
    grade = Grade(
        "A", tuple(caps), assessment_sha256="a" * 64,
        exam_item_counts=tuple((name, 4) for name in names),
        teaching_stages=(("A.BASE", "A.OTHER"),
                         ("A.STEP", "A.F3", "A.F4", "A.F5")),
    )
    course = Course(
        (grade,), "fixture.development/v1", "b" * 64, "c" * 64)
    adapter = SourceAdapter(
        "fixture.development-adapter/v1", "fixture.development/v1",
        ("fixture.development-oracle/v1",), "d" * 64,
    )
    registry = SourceAdapterRegistry((RegisteredSourceAdapter(
        adapter, lambda **_: (), lambda row, **_: True),))
    release = compile_factory_release(course, registry)
    target = DevelopmentalTarget(
        "DEV.STEP", 1, "Fixture step",
        ("A.BASE", "A.OTHER"),
        (RepresentationLayer.SEMANTIC_IDENTITY,
         RepresentationLayer.STRUCTURAL_COMPOSITION),
        (UnderstandingProjection.TRANSFER,
         UnderstandingProjection.COUNTERFACTUAL),
        ("fixture source contract",),
        "Prove binding without creating runtime authority.",
    )
    staircase = DevelopmentalStaircase(
        "fixture.development-staircase/v1",
        ("A.BASE", "A.OTHER"),
        (target,),
    )
    return release, staircase, target


class DevelopmentalReleaseBindingTests(unittest.TestCase):
    def test_source_grounded_binding_becomes_executable_frontier_only_after_baseline(self):
        release, staircase, target = fixture()
        contract = contract_for_target(target, capability_id="A.STEP")
        understanding = plan_understanding_evidence(
            contract,
            generation_axes=("source-valid", "fresh-seed"),
            supported_projections=tuple(target.projections),
        )
        plan = bind_developmental_release(
            staircase, release,
            bindings=(DevelopmentalBinding("DEV.STEP", "A.STEP"),),
            understanding_plans=(understanding,),
        )
        self.assertEqual(plan.frontier(("A.BASE",)), ())
        frontier = plan.frontier(("A.BASE", "A.OTHER"))
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0].capability_id, "A.STEP")
        self.assertTrue(frontier[0].executable)

    def test_unbound_target_is_explicit_source_binding_debt(self):
        release, staircase, _ = fixture()
        plan = bind_developmental_release(
            staircase, release, bindings=(), understanding_plans=())
        frontier = plan.frontier(("A.BASE", "A.OTHER"))
        self.assertEqual(frontier[0].capability_id, None)
        self.assertEqual(
            frontier[0].blockers,
            ("DEV.STEP:FACTORY_BINDING_REQUIRED",),
        )
        self.assertFalse(frontier[0].executable)

    def test_projection_gap_remains_nonexecutable_after_factory_binding(self):
        release, staircase, target = fixture()
        understanding = plan_understanding_evidence(
            contract_for_target(target, capability_id="A.STEP"),
            generation_axes=("source-valid",),
            supported_projections=(UnderstandingProjection.TRANSFER,),
        )
        plan = bind_developmental_release(
            staircase, release,
            bindings=(DevelopmentalBinding("DEV.STEP", "A.STEP"),),
            understanding_plans=(understanding,),
        )
        frontier = plan.frontier(("A.BASE", "A.OTHER"))
        self.assertFalse(frontier[0].executable)
        self.assertIn(
            "A.STEP:COUNTERFACTUAL:SOURCE_PROJECTION_UNSUPPORTED",
            frontier[0].blockers,
        )

    def test_binding_cannot_lie_about_factory_prerequisites(self):
        release, staircase, target = fixture()
        understanding = plan_understanding_evidence(
            contract_for_target(target, capability_id="A.F3"),
            generation_axes=("source-valid",),
            supported_projections=tuple(target.projections),
        )
        with self.assertRaisesRegex(
                ValueError, "PREREQUISITE_MISMATCH"):
            bind_developmental_release(
                staircase, release,
                bindings=(DevelopmentalBinding("DEV.STEP", "A.F3"),),
                understanding_plans=(understanding,),
            )

    def test_binding_cannot_silently_add_extra_prerequisites(self):
        release, staircase, target = fixture()
        altered = tuple(
            Capability(
                **{
                    **cap.__dict__,
                    "prerequisites": (
                        ("A.BASE", "A.OTHER", "A.F3")
                        if cap.id == "A.STEP" else cap.prerequisites),
                }
            )
            for cap in release.course.grades[0].capabilities
        )
        # Rebuild a valid staged course where the extra prerequisite is earlier.
        reordered = (
            altered[0], altered[1], altered[3],
            altered[2], altered[4], altered[5],
        )
        grade = Grade(
            "A", reordered, assessment_sha256="f" * 64,
            exam_item_counts=tuple((cap.id, 4) for cap in reordered),
            teaching_stages=(
                ("A.BASE", "A.OTHER", "A.F3"),
                ("A.STEP", "A.F4", "A.F5"),
            ),
        )
        course = Course(
            (grade,), "fixture.development-extra/v1",
            "b" * 64, "c" * 64)
        adapter = SourceAdapter(
            "fixture.development-extra-adapter/v1",
            "fixture.development/v1",
            ("fixture.development-oracle/v1",), "d" * 64,
        )
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            adapter, lambda **_: (), lambda row, **_: True),))
        extra_release = compile_factory_release(course, registry)
        understanding = plan_understanding_evidence(
            contract_for_target(target, capability_id="A.STEP"),
            generation_axes=("source-valid",),
            supported_projections=tuple(target.projections),
        )
        with self.assertRaisesRegex(
                ValueError, "PREREQUISITE_MISMATCH"):
            bind_developmental_release(
                staircase, extra_release,
                bindings=(DevelopmentalBinding("DEV.STEP", "A.STEP"),),
                understanding_plans=(understanding,),
            )

    def test_binding_projects_exact_understanding_contract_into_autonomy(self):
        release, staircase, target = fixture()
        understanding = plan_understanding_evidence(
            contract_for_target(target, capability_id="A.STEP"),
            generation_axes=("source-valid",),
            supported_projections=tuple(target.projections),
        )
        plan = bind_developmental_release(
            staircase, release,
            bindings=(DevelopmentalBinding("DEV.STEP", "A.STEP"),),
            understanding_plans=(understanding,),
        )
        specs, debt = plan.autonomy_inputs()
        self.assertEqual(debt, ())
        self.assertEqual(
            tuple(item.projection_id for item in specs),
            ("TRANSFER", "COUNTERFACTUAL"),
        )
        self.assertEqual(
            {item.capability_id for item in specs},
            {"A.STEP"},
        )

    def test_binding_projection_contract_is_real_autonomy_work(self):
        release, staircase, target = fixture()
        understanding = plan_understanding_evidence(
            contract_for_target(target, capability_id="A.STEP"),
            generation_axes=("source-valid", "fresh-seed"),
            supported_projections=tuple(target.projections),
        )
        development = bind_developmental_release(
            staircase, release,
            bindings=(DevelopmentalBinding("DEV.STEP", "A.STEP"),),
            understanding_plans=(understanding,),
        )
        specs, debt = development.autonomy_inputs()
        plan = compile_autonomy_plan(
            release, projection_evidence=specs,
            projection_coverage_debt=debt)
        ledger = initial_evidence_ledger(release, plan=plan)
        index = 0

        def pass_one(work):
            nonlocal index, ledger
            index += 1
            receipt = EvidenceReceipt(
                obligation_id=work.obligation.obligation_id,
                evidence_id=f"binding-proof-{index}",
                checkpoint_sha256="e" * 64,
                optimizer_step=index,
                cohort_sha256=hashlib.sha256(
                    f"binding-cohort-{index}".encode()).hexdigest(),
                specimen_count=work.obligation.minimum_specimens,
                passed=True,
            )
            ledger = record_evidence(
                release, ledger, receipt, plan=plan)

        while True:
            work = next_work(release, ledger, plan=plan)
            if work.capability_id == "A.STEP":
                break
            pass_one(work)

        seen = []
        while True:
            work = next_work(release, ledger, plan=plan)
            if work is None or work.capability_id != "A.STEP":
                break
            seen.append((work.obligation.kind, work.obligation.key))
            pass_one(work)

        self.assertEqual(
            seen,
            [
                (EvidenceKind.DIRECT, "source.direct"),
                (EvidenceKind.PROJECTION, "TRANSFER"),
                (EvidenceKind.PROJECTION, "COUNTERFACTUAL"),
                (EvidenceKind.PREREQUISITE, "A.BASE"),
                (EvidenceKind.PREREQUISITE, "A.OTHER"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
