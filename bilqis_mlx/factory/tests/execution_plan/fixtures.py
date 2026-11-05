"""Public synthetic course/source fixtures; no student or source admission."""
from bilqis_mlx.curriculum import (AnswerFamily, BINARY, BOOLEAN_OPERATORS, Capability, Course, Grade)
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.model import SourceAdapter


def _fixture_rows(*, capability, seed, each, **_):
    return tuple({
        "id": f"{capability}:{seed}:{index}",
        "capability": capability,
        "gold": "TRUE" if index % 2 else "FALSE",
    } for index in range(each))

def _fixture_check(row, **_):
    return row["gold"] in BINARY

def _boolean_fixture_rows(*, capability, seed, each,
                          profile_parameters=None, **_):
    operators = tuple(
        (profile_parameters or {}).get("operators", BOOLEAN_OPERATORS))
    rows = []
    for index in range(each):
        operator = operators[index % len(operators)]
        if capability == "B.IDBOOLOPS":
            rows.append({
                "id": f"{capability}:{seed}:{index}",
                "capability": capability,
                "answer_kind": "boolean_operator",
                "operator": operator,
                "gold": operator,
            })
        else:
            rows.append({
                "id": f"{capability}:{seed}:{index}",
                "capability": capability,
                "answer_kind": "binary",
                "operator": operator,
                "gold": "TRUE" if index % 2 else "FALSE",
            })
    return tuple(rows)

def _boolean_fixture_check(row, **_):
    if row.get("answer_kind") == "boolean_operator":
        return row.get("gold") in BOOLEAN_OPERATORS
    return row.get("gold") in BINARY

def _synthetic_course(count=7):
    capabilities = tuple(Capability(
        id=f"Z.C{index}", difficulty="fixture", source_anchor="repo:fixture/z",
        taught_roots=(f"z.op.{index}",), examined_roots=(f"z.op.{index}",),
        prerequisites=(), composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="fixture.z-generator/v1",
        independent_oracle="fixture.z-oracle/v1",
    ) for index in range(count))
    grade = Grade(
        "Z", capabilities, assessment_sha256="a" * 64,
        exam_item_counts=tuple((cap.id, 4) for cap in capabilities))
    return Course((grade,), "fixture.z/v1", "b" * 64, "a" * 64)

def _synthetic_registry():
    descriptor = SourceAdapter(
        "fixture.z-adapter/v1", "fixture.z-generator/v1",
        ("fixture.z-oracle/v1",), "d" * 64)
    return SourceAdapterRegistry((
        RegisteredSourceAdapter(descriptor, _fixture_rows, _fixture_check,
            semantic_footprint=lambda row: ("z.op." + row["capability"].partition(".C")[2],)),
    ))

def _synthetic_boolean_course():
    a_caps = tuple(Capability(
        id=f"A.C{index}", difficulty="fixture-a", source_anchor="repo:fixture/a",
        taught_roots=(f"a.op.{index}",), examined_roots=(f"a.op.{index}",),
        prerequisites=(), composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="fixture.a-generator/v1",
        independent_oracle="fixture.a-oracle/v1",
    ) for index in range(6))
    grade_a = Grade(
        "A", a_caps, assessment_sha256="1" * 64,
        exam_item_counts=tuple((cap.id, 12) for cap in a_caps))
    names = (
        "B.NOT", "B.AND", "B.OR", "B.XOR", "B.IMPLIES", "B.IFF",
        "B.COMPOSITE", "B.IDBOOLOPS",
    )
    b_caps = tuple(Capability(
        id=name, difficulty="fixture-b", source_anchor="repo:fixture/b",
        taught_roots=(f"b.op.{index}",), examined_roots=(f"b.op.{index}",),
        prerequisites=("A.C0", "A.C1"), composed_of=(),
        answer_families=(
            (AnswerFamily("boolean_operator", BOOLEAN_OPERATORS),)
            if name == "B.IDBOOLOPS"
            else (AnswerFamily("binary", BINARY),)
        ),
        lesson_generator="fixture.b-generator/v1",
        independent_oracle="fixture.b-oracle/v1",
    ) for index, name in enumerate(names))
    grade_b = Grade(
        "B", b_caps, assessment_sha256="2" * 64,
        exam_item_counts=tuple((cap.id, 12) for cap in b_caps),
        teaching_stages=(
            names[:6],
            ("B.COMPOSITE",),
            ("B.IDBOOLOPS",),
        ))
    course = Course(
        (grade_a, grade_b), "fixture.a-b/v1",
        source_attestation_sha256="3" * 64,
        assessment_manifest_sha256="2" * 64)
    roots = {cap.id: cap.taught_roots for grade in course.grades for cap in grade.capabilities}
    registry = SourceAdapterRegistry((
        RegisteredSourceAdapter(SourceAdapter(
            "fixture.a-adapter/v1", "fixture.a-generator/v1",
            ("fixture.a-oracle/v1",), "4" * 64), _fixture_rows, _fixture_check,
            semantic_footprint=lambda row: roots[row["capability"]]),
        RegisteredSourceAdapter(SourceAdapter(
            "fixture.b-adapter/v1", "fixture.b-generator/v1",
            ("fixture.b-oracle/v1",), "5" * 64,
            profile_dimensions=(("operators", BOOLEAN_OPERATORS),)),
            _boolean_fixture_rows, _boolean_fixture_check,
            semantic_footprint=lambda row: roots[row["capability"]]),
    ))
    return course, registry

for _fixture in (_fixture_rows, _fixture_check, _boolean_fixture_rows, _boolean_fixture_check, _synthetic_course, _synthetic_registry, _synthetic_boolean_course):
    _fixture.__module__ = "bilqis_mlx.factory.tests.test_execution_plan"
del _fixture
