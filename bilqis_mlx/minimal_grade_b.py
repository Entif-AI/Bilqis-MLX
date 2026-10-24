"""Reduced Grade-B release: AND, IFF, COMPOSITE and IDBOOLOPS only."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from .boolean_composite import (
    draw_composite,
    constructor_digest as parent_composite_constructor_digest,
)
from .boolean_composite_oracle import VERSION as COMPOSITE_ORACLE
from .boolean_composite_oracle import evaluate as evaluate_composite
from .boolean_identification import (
    draw_identification,
    constructor_digest as parent_identification_constructor_digest,
)
from .curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from .grade_a_probe import read_sources
from .grade_b_oracle import VERSION as BOOLEAN_ORACLE
from .live_grade_b import (
    PREREQUISITES,
    draw_connectives,
    constructor_digest as parent_boolean_constructor_digest,
    source_attestation,
)
from .minimal_boolean_identification_oracle import (
    OPERATORS,
    VERSION as IDENTIFICATION_ORACLE,
    evaluate as evaluate_identification,
)


GENERATOR = "bilqis.mlx.grade-b-minimal-constructor/v1"
RELEASE = "bilqis.mlx.grade-a-b-minimal/20261019-v1"
ASSESSMENT_ITEMS = 12
CAPABILITIES = ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
COMPOSITE = "B.COMPOSITE"
IDENTIFICATION = "B.IDBOOLOPS"
ANSWER_KIND = "boolean_operator"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def constructor_digest() -> str:
    home = Path(__file__).resolve().parent
    return _digest({
        "files": {
            name: hashlib.sha256((home / name).read_bytes()).hexdigest()
            for name in ("minimal_grade_b.py", "minimal_boolean_identification_oracle.py")
        },
        "parent_boolean_constructor_sha256": parent_boolean_constructor_digest(),
        "parent_composite_constructor_sha256": parent_composite_constructor_digest(),
        "parent_identification_constructor_sha256":
            parent_identification_constructor_digest(),
    })


def answer_heads(graph: dict) -> dict:
    names = list(graph["tokens"])
    operator_tokens = ["cogal.operator." + operator for operator in OPERATORS]
    required = ["cogal.value.false", "cogal.value.true", *operator_tokens]
    if any(name not in names for name in required):
        raise ValueError("GRADE_B_MINIMAL_ANSWER_HEAD_TOKEN_MISSING")
    return {
        "semantic_token": {"values": names, "token_ids": list(range(len(names)))},
        "binary": {
            "values": list(BINARY),
            "token_ids": [names.index("cogal.value.false"),
                          names.index("cogal.value.true")],
        },
        ANSWER_KIND: {
            "values": list(OPERATORS),
            "token_ids": [names.index(name) for name in operator_tokens],
        },
    }


def _atomic_rows(source_root: Path, graph: dict, *, capability: str,
                 seed: int, each: int) -> tuple[dict, ...]:
    rows = draw_connectives(
        source_root, graph, seed=seed, capability=capability, each=each)
    return tuple({**row, "generator": GENERATOR} for row in rows)


def _composite_rows(source_root: Path, graph: dict, *, seed: int,
                    each: int) -> tuple[dict, ...]:
    rows = draw_composite(
        source_root, graph, seed=seed, each=each,
        capability=COMPOSITE, operators=OPERATORS)
    return tuple({**row, "generator": GENERATOR} for row in rows)


def _identification_rows(source_root: Path, graph: dict, *, seed: int,
                         each: int) -> tuple[dict, ...]:
    rows = draw_identification(
        source_root, graph, seed=seed, each=each,
        capability=IDENTIFICATION, operators=OPERATORS)
    result = tuple({**row, "generator": GENERATOR,
                    "oracle": IDENTIFICATION_ORACLE} for row in rows)
    if any(evaluate_identification(row["record"]) != row["gold"] for row in result):
        raise ValueError(IDBOOLOPS_ORACLE_DRIFT)
    return result


def draw_minimal(source_root: Path, graph: dict, *, seed: int,
                 each: int = ASSESSMENT_ITEMS,
                 capability: str | None = None) -> tuple[dict, ...]:
    if type(seed) is not int or type(each) is not int or each < 1:
        raise ValueError("GRADE_B_MINIMAL_INVALID_DRAW")
    selected = CAPABILITIES if capability is None else (capability,)
    if any(cap not in CAPABILITIES for cap in selected):
        raise ValueError("GRADE_B_MINIMAL_UNKNOWN_CAPABILITY")
    rows = []
    for index, cap in enumerate(selected):
        cap_seed = int(_digest([seed, cap, index])[:16], 16)
        if cap in ("B.AND", "B.IFF"):
            rows.extend(_atomic_rows(
                source_root, graph, capability=cap, seed=cap_seed, each=each))
        elif cap == COMPOSITE:
            rows.extend(_composite_rows(source_root, graph, seed=cap_seed, each=each))
        else:
            rows.extend(_identification_rows(
                source_root, graph, seed=cap_seed, each=each))
    return tuple(rows)


def build_course(grade_a: Course, source_root: Path) -> Course:
    if (grade_a.program_complete or len(grade_a.grades) != 1 or
            grade_a.grades[0].id != "A" or not grade_a.executable):
        raise ValueError("GRADE_B_MINIMAL_PREDECESSOR_NOT_ADMITTED_GRADE_A")
    provenance = source_attestation(source_root)
    _, _, graph, _, _ = read_sources(source_root)
    witness = draw_minimal(source_root, graph, seed=2026101903)
    if len(witness) != len(CAPABILITIES) * ASSESSMENT_ITEMS:
        raise ValueError("GRADE_B_MINIMAL_ADMISSION_COHORT_INCOMPLETE")
    difficulty = "first-boolean-composition"
    atomic = tuple(Capability(
        id=cap, difficulty=difficulty,
        source_anchor="repo:bilqis_logic/kernel.py::TABLES+encode",
        taught_roots=("cogal.operator." + cap.removeprefix("B."),),
        examined_roots=("cogal.operator." + cap.removeprefix("B."),),
        prerequisites=PREREQUISITES, composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator=GENERATOR, independent_oracle=BOOLEAN_ORACLE,
    ) for cap in ("B.AND", "B.IFF"))
    roots = tuple("cogal.operator." + op for op in OPERATORS)
    composite = Capability(
        id=COMPOSITE, difficulty=difficulty,
        source_anchor="repo:bilqis_logic/kernel.py::TABLES+encode",
        taught_roots=roots, examined_roots=roots,
        prerequisites=(*PREREQUISITES, "B.AND", "B.IFF"), composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator=GENERATOR, independent_oracle=COMPOSITE_ORACLE,
    )
    identification = Capability(
        id=IDENTIFICATION, difficulty=difficulty,
        source_anchor="repo:bilqis_logic/kernel.py::TABLES+_operation",
        taught_roots=roots, examined_roots=roots,
        prerequisites=(*PREREQUISITES, "B.AND", "B.IFF"), composed_of=(),
        answer_families=(AnswerFamily(ANSWER_KIND, OPERATORS),),
        lesson_generator=GENERATOR, independent_oracle=IDENTIFICATION_ORACLE,
    )
    caps = (*atomic, composite, identification)
    seal = _digest({
        "generator": GENERATOR, "generator_code_sha256": constructor_digest(),
        "source_attestation": provenance, "source_witness_sha256": _digest(witness),
        "prior_a_rubric": grade_a.grades[0].assessment_sha256,
        "items_per_capability": ASSESSMENT_ITEMS,
        "operators": OPERATORS,
    })
    grade_b = Grade(
        "B", caps, assessment_sha256=seal,
        exam_item_counts=tuple((cap.id, ASSESSMENT_ITEMS) for cap in caps),
        teaching_stages=(("B.AND", "B.IFF"), (COMPOSITE,), (IDENTIFICATION,)),
    )
    course = replace(
        grade_a, grades=(*grade_a.grades, grade_b), version=RELEASE,
        program_complete=False,
        source_attestation_sha256=_digest({
            "grade_a": grade_a.source_attestation_sha256,
            "grade_b_minimal": provenance,
        }),
        assessment_manifest_sha256=seal,
    )
    if not course.executable:
        raise ValueError("GRADE_B_MINIMAL_RELEASE_NOT_EXECUTABLE")
    return course
IDBOOLOPS_ORACLE_DRIFT = "GRADE_B_MINIMAL_IDBOOLOPS_ORACLE_DRIFT"
