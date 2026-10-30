from dataclasses import replace
import unittest

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.generation import draw_release_rows
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.curriculum.scheduler import Assessment, Score, assess, start_new, visit


def _rows(*, capability, seed, each, **_):
    return tuple({"id": f"{capability}:{seed}:{i}", "capability": capability,
                  "gold": "TRUE" if i % 2 else "FALSE"}
                 for i in range(each))


def _check(row, **_):
    return row["gold"] == ("TRUE" if int(row["id"].rsplit(":", 1)[1]) % 2 else "FALSE")


class GenericGenerationTests(unittest.TestCase):
    def test_generation_refuses_registry_implementation_drift(self):
        course, registered = synthetic_release_inputs()
        release = compile_factory_release(course, registered)
        descriptor = replace(release.source_adapters[0], implementation_sha256="f" * 64)
        called = []
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            descriptor, lambda **kwargs: called.append(kwargs), _check),))
        with self.assertRaisesRegex(ValueError, "FACTORY_GENERATION_ADAPTER_DRIFT"):
            draw_release_rows(None, {}, release, registry, seed=1)
        self.assertEqual(called, [])

    def test_unchanged_descriptor_cannot_hide_wrong_source_gold(self):
        course, registered = synthetic_release_inputs()
        release = compile_factory_release(course, registered)

        def corrupted(**kwargs):
            rows = list(_rows(**kwargs))
            rows[0]["gold"] = "TRUE"  # index zero independently means FALSE.
            return tuple(rows)

        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            release.source_adapters[0], corrupted, _check),))
        with self.assertRaisesRegex(ValueError, "SOURCE_ORACLE_DISAGREEMENT"):
            draw_release_rows(None, {}, release, registry, seed=1)

    def test_generation_rejects_duplicate_row_identity_from_adapter(self):
        course, registered = synthetic_release_inputs()
        release = compile_factory_release(course, registered)

        def duplicate_identity(**kwargs):
            rows = list(_rows(**kwargs))
            rows[1] = dict(rows[0])
            return tuple(rows)

        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            release.source_adapters[0], duplicate_identity,
            lambda row, **_: True),))
        with self.assertRaisesRegex(
                ValueError, "FACTORY_GENERATION_IDENTITY_COLLISION"):
            draw_release_rows(None, {}, release, registry, seed=1)

    def test_synthetic_grade_uses_only_declarative_adapter_registration(self):
        caps = tuple(Capability(
            id=f"Z.C{i}", difficulty="fixture", source_anchor="repo:fixture/z",
            taught_roots=(f"z.op.{i}",), examined_roots=(f"z.op.{i}",),
            prerequisites=(), composed_of=(),
            answer_families=(AnswerFamily("binary", BINARY),),
            lesson_generator="fixture.z-generator/v1", independent_oracle="fixture.z-oracle/v1",
        ) for i in range(6))
        grade = Grade("Z", caps, assessment_sha256="a" * 64,
                      exam_item_counts=tuple((cap.id, 4) for cap in caps))
        course = Course((grade,), "fixture.z/v1", "b" * 64, "a" * 64)
        adapter = SourceAdapter("fixture.z-adapter/v1", "fixture.z-generator/v1",
                                ("fixture.z-oracle/v1",), "d" * 64)
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(adapter, _rows, _check),))
        release = compile_factory_release(course, registry)
        rows = draw_release_rows(None, {}, release, registry, seed=17)
        self.assertEqual(len(rows), 24)
        self.assertEqual({row["capability"] for row in rows}, {cap.id for cap in caps})
        student = Checkpoint("e" * 64, "bundles/z-fixture", 0, True)
        state = start_new(course, student)
        self.assertEqual(state.grade, "Z")
        for capability in tuple(cap.id for cap in caps):
            self.assertEqual(state.queue[0], capability)
            state = visit(course, state, capability, student)
        snapshot = Assessment(
            checkpoint_sha256=student.sha256,
            optimizer_step=student.optimizer_step,
            course_digest=course.digest(),
            rubric_digest=grade.assessment_sha256,
            scores={cap.id: Score(4, 4) for cap in caps},
            evaluation_id="fixture-z-perfect")
        finished = assess(course, state, snapshot)
        while finished.stage == "PROMOTION_SWEEP":
            finished = visit(course, finished, finished.queue[0], student)
            finished = assess(course, finished, snapshot)
        self.assertEqual(finished.stage, "AWAITING_NEXT_GRADE")


if __name__ == "__main__":
    unittest.main()
