"""Versioned inverse Boolean-operator identification capability for Grade B."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path
import random

from .boolean_composite import RELEASE as PARENT_RELEASE
from .boolean_composite import constructor_digest as parent_composite_constructor_digest
from .boolean_identification_oracle import TASK, VERSION as ORACLE
from .boolean_identification_oracle import evaluate as independent_evaluate
from .curriculum import AnswerFamily, BINARY, BOOLEAN_OPERATORS, Capability, Course
from .grade_a_probe import read_sources
from .live_grade_b import PREREQUISITES, source_attestation


CAPABILITY = "B.IDBOOLOPS"
GENERATOR = "bilqis.mlx.grade-b-idboolops-constructor/v1"
RELEASE = "bilqis.mlx.grade-a-b-idboolops/20261019-v1"
ANSWER_KIND = "boolean_operator"
ASSESSMENT_ITEMS = 12


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def constructor_digest() -> str:
    home = Path(__file__).resolve().parent
    return _digest({
        "files": {name: hashlib.sha256((home / name).read_bytes()).hexdigest()
                  for name in ("boolean_identification.py", "boolean_identification_oracle.py")},
        "parent_boolean_composite_constructor_sha256": parent_composite_constructor_digest(),
    })


def _logic_source(legacy_root: Path):
    source_attestation(legacy_root)
    module = importlib.import_module("bilqis_logic.kernel")
    expected = Path(legacy_root).resolve() / "bilqis_logic/kernel.py"
    if Path(module.__file__).resolve() != expected:
        raise ValueError("GRADE_B_IDBOOLOPS_BOOLEAN_SOURCE_ROOT_MISMATCH")
    return module


def _require_historical_graph(legacy_root: Path, graph: dict):
    _, _, source_graph, _, _ = read_sources(legacy_root)
    if (graph["tokens"][:len(source_graph["tokens"])] != source_graph["tokens"] or
            len(graph["tokens"]) < len(source_graph["tokens"])):
        raise ValueError("GRADE_B_IDBOOLOPS_FROZEN_TOKEN_PREFIX_MISMATCH")


def _operator_domain(operators) -> tuple[str, ...]:
    operators = tuple(operators)
    if (len(operators) < 2 or len(set(operators)) != len(operators) or
            not set(operators) <= set(BOOLEAN_OPERATORS) or
            operators != tuple(
                operator for operator in BOOLEAN_OPERATORS
                if operator in operators)):
        raise ValueError("GRADE_B_IDBOOLOPS_OPERATOR_DOMAIN_INVALID")
    return operators


def answer_heads(graph: dict, operators=BOOLEAN_OPERATORS) -> dict:
    """Restrict the typed readout to existing Boolean semantic-token identities."""
    operators = _operator_domain(operators)
    names = list(graph["tokens"])
    operator_tokens = ["cogal.operator." + operator for operator in operators]
    required = ["cogal.value.false", "cogal.value.true", *operator_tokens]
    if any(name not in names for name in required):
        raise ValueError("GRADE_B_IDBOOLOPS_ANSWER_HEAD_TOKEN_MISSING")
    return {
        "semantic_token": {"values": names, "token_ids": list(range(len(names)))},
        "binary": {"values": list(BINARY),
                   "token_ids": [names.index("cogal.value.false"),
                                 names.index("cogal.value.true")]},
        ANSWER_KIND: {"values": list(operators),
                      "token_ids": [names.index(name) for name in operator_tokens]},
    }


def _apply(operator: str, values: tuple[bool, ...]) -> bool:
    if operator == "NOT":
        return not values[0]
    left, right = values
    return {
        "AND": lambda: left and right,
        "OR": lambda: left or right,
        "XOR": lambda: left != right,
        "IMPLIES": lambda: (not left) or right,
        "IFF": lambda: left == right,
    }[operator]()


def encode_record(record: dict, legacy_root: Path, graph: dict) -> list[int]:
    """Serialize direct Boolean truth signatures with the operator hidden."""
    _require_historical_graph(legacy_root, graph)
    if (record.get("task") != TASK or "world" in record or
            set(record) != {"task", "observations", "options"}):
        raise ValueError("GRADE_B_IDBOOLOPS_RECORD_SHAPE")
    names = graph["tokens"]
    premise = names.index("micro.proof.premise")
    conclusion = names.index("micro.proof.conclusion")
    separator = names.index("syntax.separator")
    end = names.index("syntax.end")
    false_id = names.index("cogal.value.false")
    true_id = names.index("cogal.value.true")
    tokens = [names.index("task.evaluate")]
    observations = record.get("observations") or []
    if not observations:
        raise ValueError("GRADE_B_IDBOOLOPS_OBSERVATIONS_MISSING")
    for observation in observations:
        operands = observation.get("operands")
        if (not isinstance(operands, list) or len(operands) != 2 or
                any(not isinstance(item, dict) or item.get("kind") != "literal" or
                    type(item.get("value")) is not bool for item in operands)):
            raise ValueError("GRADE_B_IDBOOLOPS_OBSERVATION_SHAPE")
        for operand in operands:
            tokens.extend((premise, true_id if operand["value"] else false_id))
        tokens.extend((conclusion, true_id if observation["result"] else false_id,
                       separator))
    tokens[-1] = end
    if not 1 <= len(tokens) <= 96:
        raise ValueError("GRADE_B_IDBOOLOPS_CONTEXT_LENGTH")
    return tokens


def _cycle(legacy_root: Path, graph: dict, *, seed: int, cycle: int,
           operators=BOOLEAN_OPERATORS) -> tuple[dict, ...]:
    operators = _operator_domain(operators)
    _require_historical_graph(legacy_root, graph)
    logic = _logic_source(legacy_root)
    material = ([GENERATOR, seed, cycle]
                if operators == tuple(BOOLEAN_OPERATORS)
                else [GENERATOR, "profile", list(operators), seed, cycle])
    rng = random.Random(_digest(material))
    copies, remainder = divmod(ASSESSMENT_ITEMS, len(operators))
    schedule = list(operators) * copies + list(operators[:remainder])
    rng.shuffle(schedule)
    counts = Counter(schedule)
    if (set(counts) != set(operators) or
            max(counts.values()) - min(counts.values()) > 1):
        raise ValueError("GRADE_B_IDBOOLOPS_OPERATOR_BALANCE_DRIFT")
    rows = []
    for target in schedule:
        # Keep the experimental surface arity-neutral. NOT uses the first
        # proposition and ignores the controlled second proposition; all six
        # primitives therefore expose a unique four-bit FF/FT/TF/TT signature.
        patterns = [(False, False), (False, True), (True, False), (True, True)]
        rng.shuffle(patterns)
        for _ in range(5000):
            rng.shuffle(patterns)
            observations = []
            for pattern in patterns:
                generator_truth = _apply(target, pattern)
                source_values = ((pattern[0],) if target == "NOT" else pattern)
                source_expr = logic.apply(
                    target, *(logic.literal(bit) for bit in source_values))
                if (logic.evaluate(source_expr, {}) != generator_truth or
                        logic.independent_evaluate(source_expr, {}) != generator_truth):
                    raise ValueError("GRADE_B_IDBOOLOPS_SOURCE_TRUTH_DISAGREEMENT")
                observations.append({
                    "operands": [logic.literal(bit) for bit in pattern],
                    "result": generator_truth,
                })
            record = {"task": TASK, "observations": observations,
                      "options": list(operators)}
            gold = independent_evaluate(record)
            if gold != target:
                raise ValueError("GRADE_B_IDBOOLOPS_INDEPENDENT_ORACLE_DISAGREEMENT")
            tokens = encode_record(record, legacy_root, graph)
            identity = _digest(record)
            if identity not in {row["id"] for row in rows}:
                break
        else:
            raise ValueError("GRADE_B_IDBOOLOPS_VARIATION_EXHAUSTED")
        rows.append({
            "id": identity, "source_id": identity, "capability": CAPABILITY,
            "answer_kind": ANSWER_KIND, "gold": gold, "record": record,
            "tokens": tokens, "oracle": ORACLE, "generator": GENERATOR,
            "operator_options": list(operators),
            "observation_count": len(observations),
            "root": "cogal.operator." + target,
            "operator_roots": ["cogal.operator." + operator
                               for operator in operators],
        })
    return tuple(rows)


def draw_identification(legacy_root: Path, graph: dict, *, seed: int,
                        each: int = ASSESSMENT_ITEMS,
                        capability: str | None = CAPABILITY,
                        operators=BOOLEAN_OPERATORS) -> tuple[dict, ...]:
    if type(seed) is not int or type(each) is not int or each < 1:
        raise ValueError("GRADE_B_IDBOOLOPS_INVALID_DRAW")
    if capability not in (None, CAPABILITY):
        raise ValueError("GRADE_B_IDBOOLOPS_UNKNOWN_CAPABILITY")
    operators = _operator_domain(operators)
    rows, seen = [], set()
    cycle = 0
    while len(rows) < each:
        for row in _cycle(
                legacy_root, graph, seed=seed, cycle=cycle,
                operators=operators):
            if row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)
                if len(rows) == each:
                    break
        cycle += 1
    return tuple(rows)


def build_course(previous: Course, legacy_root: Path) -> Course:
    if (not isinstance(previous, Course) or previous.version != PARENT_RELEASE or
            len(previous.grades) != 2 or previous.grades[-1].id != "B" or
            len(previous.grades[-1].capabilities) != 7 or
            previous.grades[-1].capabilities[-1].id != "B.COMPOSITE"):
        raise ValueError("GRADE_B_IDBOOLOPS_REQUIRES_COMPOSITE_PARENT")
    _, _, graph, _, _ = read_sources(legacy_root)
    witness = draw_identification(legacy_root, graph, seed=2026101902)
    roots = tuple("cogal.operator." + operator for operator in BOOLEAN_OPERATORS)
    cap = Capability(
        id=CAPABILITY, difficulty=previous.grades[-1].capabilities[0].difficulty,
        source_anchor="repo:bilqis_logic/kernel.py::TABLES+_operation",
        taught_roots=roots, examined_roots=roots, prerequisites=PREREQUISITES,
        composed_of=(),
        answer_families=(AnswerFamily(ANSWER_KIND, BOOLEAN_OPERATORS),),
        lesson_generator=GENERATOR, independent_oracle=ORACLE,
    )
    existing = tuple(replace(item, lesson_generator=GENERATOR)
                     for item in previous.grades[-1].capabilities)
    counts = (*previous.grades[-1].exam_item_counts, (CAPABILITY, ASSESSMENT_ITEMS))
    seal = _digest({
        "parent_course_sha256": previous.digest(),
        "parent_b_rubric": previous.grades[-1].assessment_sha256,
        "generator": GENERATOR, "generator_code_sha256": constructor_digest(),
        "source_witness_sha256": _digest(witness),
        "items_per_capability": ASSESSMENT_ITEMS,
        "answer_kind": ANSWER_KIND,
    })
    grade = replace(previous.grades[-1], capabilities=(*existing, cap),
                    assessment_sha256=seal, exam_item_counts=counts,
                    teaching_stages=())
    course = replace(previous, grades=(*previous.grades[:-1], grade),
                     version=RELEASE, assessment_manifest_sha256=seal)
    if not course.executable:
        raise ValueError("GRADE_B_IDBOOLOPS_RELEASE_NOT_EXECUTABLE")
    return course
