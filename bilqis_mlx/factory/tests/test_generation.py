import unittest

from bilqis_mlx.champions import Checkpoint
from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.generation import draw_release_rows
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.school import Assessment, Score, assess, start_new, visit


def _rows(*, capability, seed, each, **_):
    return tuple({"id": f"{capability}:{seed}:{i}", "capability": capability,
                  "gold": "TRUE" if i % 2 else "FALSE"}
                 for i in range(each))


class GenericGenerationTests(unittest.TestCase):
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
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(adapter, _rows),))
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
        self.assertEqual(finished.stage, "AWAITING_NEXT_GRADE")


if __name__ == "__main__":
    unittest.main()
