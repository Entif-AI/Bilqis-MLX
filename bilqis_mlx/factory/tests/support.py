"""Minimal source-declared course shared by factory and admission contract tests."""
from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.model import SourceAdapter


def synthetic_release_inputs():
    caps = tuple(Capability(
        id=f"A.C{i}", difficulty="fixture", source_anchor="repo:fixture/source",
        taught_roots=(f"fixture.op.{i}",), examined_roots=(f"fixture.op.{i}",),
        prerequisites=(), composed_of=(), answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="fixture.generator/v1", independent_oracle="fixture.oracle/v1",
    ) for i in range(6))
    grade = Grade("A", caps, assessment_sha256="a" * 64,
                  exam_item_counts=tuple((cap.id, 4) for cap in caps))
    course = Course((grade,), "fixture.course/v1", "b" * 64, "c" * 64)
    descriptor = SourceAdapter("fixture.adapter/v1", "fixture.generator/v1",
                               ("fixture.oracle/v1",), "d" * 64)
    registry = SourceAdapterRegistry((RegisteredSourceAdapter(
        descriptor, lambda **_: (), lambda row, **_: False),))
    return course, registry
