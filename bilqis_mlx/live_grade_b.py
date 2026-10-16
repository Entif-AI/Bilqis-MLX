"""Source-oracled, dynamically sampled Grade B truth-functional constructors.

Only already mastered Grade A operand semantics are used: entity identity,
direct PARENT and undirected LINK. All six connective operators have stable
legacy token identities and formal typed semantics; no unattested NI wordform
or permanently embargoed examination question is introduced.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from .curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from .grade_a_probe import PINNED_SOURCES, read_sources
from .grade_b_oracle import CONNECTIVES, VERSION as ORACLE_VERSION
from .grade_b_oracle import evaluate as independent_oracle, operand_truth

GENERATOR = "bilqis.mlx.grade-b-connectives-constructor/v1"
RELEASE = "bilqis.mlx.grade-a-b-live/20261015-v1"
ASSESSMENT_ITEMS_PER_CAPABILITY = 12
PREREQUISITES = ("A.IDENTITY", "A.PARENT", "A.LINK")
PINNED_BOOLEAN_SOURCE = PINNED_SOURCES["bilqis_logic/kernel.py"]


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def constructor_digest():
    home = Path(__file__).resolve().parent
    return _digest({p: hashlib.sha256((home / p).read_bytes()).hexdigest()
                    for p in ("live_grade_b.py", "grade_b_oracle.py")})


def source_attestation(legacy_root: Path) -> dict:
    """Fail closed unless the exact old source and graph are still available."""
    root = Path(legacy_root).resolve(strict=True)
    micro, _, graph, sha, graph_sha = read_sources(root)
    source = root / "bilqis_logic/kernel.py"
    if hashlib.sha256(source.read_bytes()).hexdigest() != PINNED_BOOLEAN_SOURCE:
        raise ValueError("GRADE_B_BOOLEAN_TRUTH_TABLE_SOURCE_DRIFT")
    required = ("micro.compare.EQ", "micro.relation.PARENT", "micro.relation.LINK")
    identities = tuple("cogal.operator." + op for op in CONNECTIVES)
    if not set(required + identities) <= set(graph["tokens"]):
        raise ValueError("GRADE_B_SOURCE_TOKEN_IDENTITIES_UNAVAILABLE")
    return {"source_sha256": sha, "graph_sha256": graph_sha,
            "boolean_sha256": PINNED_BOOLEAN_SOURCE,
            "operators": list(CONNECTIVES),
            "prerequisites": list(PREREQUISITES),
            "semantic_mode": "PINNED_TYPED_FORMAL_ADAPTER_NOT_NI_WORDFORM",
            "parent_source": micro.VERSION}


def live_course(grade_a: Course, legacy_root: Path) -> Course:
    """Append one versioned grade while preserving A's actual accepted seal."""
    if (grade_a.program_complete or len(grade_a.grades) != 1 or
            grade_a.grades[0].id != "A" or
            {c.id for c in grade_a.grades[0].capabilities} != {
                "A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS"} or
            not grade_a.executable):
        raise ValueError("GRADE_B_PREDECESSOR_NOT_ADMITTED_GRADE_A")
    provenance = source_attestation(legacy_root)
    _, _, source_graph, _, _ = read_sources(legacy_root)
    # No B source is admitted from identifiers alone. Construct and verify an
    # entire complete source-oracled candidate cohort before a run may switch.
    witness = draw_connectives(legacy_root, source_graph, seed=2026101501)
    if (len(witness) != len(CONNECTIVES) * ASSESSMENT_ITEMS_PER_CAPABILITY or
            {op: sum(row["capability"] == "B." + op for row in witness)
             for op in CONNECTIVES} != {
                 op: ASSESSMENT_ITEMS_PER_CAPABILITY for op in CONNECTIVES}):
        raise ValueError("GRADE_B_SOURCE_ADMISSION_COHORT_NOT_COMPREHENSIVE")
    caps = tuple(Capability(
        id="B." + op, difficulty="first-boolean-composition",
        source_anchor="repo:bilqis_micro/kernel.py::_operation+_table",
        taught_roots=("cogal.operator." + op,),
        examined_roots=("cogal.operator." + op,),
        prerequisites=PREREQUISITES,
        composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="bilqis_mlx.live_grade_b.draw_connectives",
        independent_oracle=ORACLE_VERSION,
    ) for op in CONNECTIVES)
    seal = _digest({"generator": GENERATOR,
                    "generator_code_sha256": constructor_digest(),
                    "source_attestation": provenance,
                    "source_witness_sha256": _digest(witness),
                    "prior_a_rubric": grade_a.grades[0].assessment_sha256,
                    "items_per_capability": ASSESSMENT_ITEMS_PER_CAPABILITY})
    grade_b = Grade("B", caps, assessment_sha256=seal,
                    exam_item_counts=tuple((c.id, ASSESSMENT_ITEMS_PER_CAPABILITY)
                                            for c in caps))
    course = replace(grade_a, grades=(*grade_a.grades, grade_b),
                     version=RELEASE, program_complete=False,
                     source_attestation_sha256=_digest({
                         "grade_a": grade_a.source_attestation_sha256,
                         "grade_b": provenance}),
                     assessment_manifest_sha256=seal)
    if not course.executable:
        raise ValueError("GRADE_B_SOURCE_RELEASE_NOT_EXECUTABLE")
    return course


def _random_world(micro, rng, n):
    universe = sorted(rng.sample(tuple("ABCDE"), n))
    facts = []
    for i, a in enumerate(universe):
        for b in universe[i+1:]:
            if rng.randrange(3) == 0:
                facts.append(("PARENT", a, b) if rng.randrange(2) else ("PARENT", b, a))
            if rng.randrange(2) == 0:
                facts.append(("LINK", a, b) if rng.randrange(2) else ("LINK", b, a))
    return micro.world(universe, facts)


def _operand(micro, rng, world):
    a, b = rng.sample(world["entities"], 2)
    kind = rng.choice(("EQ", "PARENT", "LINK"))
    if kind == "EQ":
        return micro.compare("EQ", micro.entity(a), micro.entity(
            a if rng.randrange(2) else b))
    return micro.relation(kind, micro.entity(a), micro.entity(b))


def draw_connectives(legacy_root: Path, graph: dict, *, seed: int,
                     each: int = ASSESSMENT_ITEMS_PER_CAPABILITY,
                     capability: str | None = None) -> tuple[dict, ...]:
    if type(seed) is not int or type(each) is not int or each < 4 or each % 2:
        raise ValueError("GRADE_B_BALANCED_EVEN_SAMPLE_REQUIRED")
    micro, _, source_graph, _, _ = read_sources(legacy_root)
    if (graph["tokens"][:len(source_graph["tokens"])] != source_graph["tokens"] or
            len(graph["tokens"]) < len(source_graph["tokens"])):
        raise ValueError("GRADE_B_FROZEN_TOKEN_PREFIX_MISMATCH")
    selected = (CONNECTIVES if capability is None else
                (capability.removeprefix("B."),))
    if not selected or any(op not in CONNECTIVES for op in selected):
        raise ValueError("GRADE_B_UNKNOWN_OPERATOR")
    result, seen = [], set()
    for op in selected:
        rng = random.Random(_digest([GENERATOR, seed, op]))
        patterns = [(False,), (True,)] if op == "NOT" else [
            (False,False), (False,True), (True,False), (True,True)]
        truth_groups = {gold: [bits for bits in patterns if independent_truth(op,bits) == gold]
                        for gold in (False, True)}
        if not all(truth_groups.values()):
            raise ValueError("GRADE_B_OPERATOR_NOT_BINARY_DISCRIMINATING")
        for index in range(each):
            expected = index % 2 == 0
            candidates = truth_groups[expected]
            pattern = candidates[(index // 2) % len(candidates)]
            n = 3 if (index // 2) % 2 == 0 else 4
            for _ in range(5000):
                world = _random_world(micro, rng, n)
                operands = tuple(_operand(micro, rng, world) for _ in pattern)
                if tuple(operand_truth(world, q) for q in operands) != pattern:
                    continue
                record = micro.record(world, micro.logic(op, *operands))
                gold = micro.evaluate(record)
                if (gold != micro.independent_evaluate(record) or
                        gold != independent_oracle(record, "B." + op) or
                        gold != ("TRUE" if expected else "FALSE")):
                    raise ValueError("GRADE_B_THREE_ORACLE_DISAGREEMENT")
                tokens = list(micro.encode(record))
                identity = _digest(record)
                if (identity in seen or not 1 <= len(tokens) <= 96 or
                        min(tokens) < 0 or max(tokens) >= len(graph["tokens"])):
                    continue
                break
            else:
                raise ValueError("GRADE_B_OPERATOR_VARIATION_EXHAUSTED:" + op)
            seen.add(identity)
            result.append({"id": identity, "source_id": identity,
                           "capability": "B." + op, "answer_kind": "binary",
                           "gold": gold, "record": record, "tokens": tokens,
                           "universe_size": n, "oracle": ORACLE_VERSION,
                           "generator": GENERATOR,
                           "operand_truths": list(pattern),
                           "root": "cogal.operator." + op})
    return tuple(result)


def independent_truth(op: str, values: tuple[bool, ...]) -> bool:
    """Pure generator-side classification used only to choose balanced cases."""
    if op == "NOT": return not values[0]
    a, b = values
    if op == "AND": return a and b
    if op == "OR": return a or b
    if op == "XOR": return a != b
    if op == "IMPLIES": return not a or b
    if op == "IFF": return a == b
    raise ValueError("GRADE_B_UNKNOWN_OPERATOR")
