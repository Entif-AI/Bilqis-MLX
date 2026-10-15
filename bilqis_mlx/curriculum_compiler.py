"""Deterministic curriculum-AST projection and source-oracled probe planner.

The Registry is editorial authority; a compiled proposal is NOT training
admission. This module has no optimizer, checkpoint, or grade-release effects.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random

from .curriculum import Course, validate


@dataclass(frozen=True)
class CapabilityNode:
    id: str
    grade: str
    roots: tuple[str, ...]
    requires: tuple[str, ...]
    composed_of: tuple[str, ...]
    answers: tuple[str, ...]
    oracle: str | None
    source: str


@dataclass(frozen=True)
class CurriculumAST:
    version: str
    nodes: tuple[CapabilityNode, ...]
    authorized_for_training: bool = False

    def digest(self):
        from dataclasses import asdict
        value = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(value.encode()).hexdigest()


def compile_ast(course: Course) -> CurriculumAST:
    """Build one canonical topological projection; never promote proposals."""
    validate(course)
    nodes = tuple(CapabilityNode(
        id=cap.id, grade=grade.id, roots=cap.taught_roots,
        requires=cap.prerequisites, composed_of=cap.composed_of,
        answers=tuple(a.kind for a in cap.answer_families),
        oracle=cap.independent_oracle, source=cap.source_anchor)
        for grade in course.grades for cap in grade.capabilities)
    return CurriculumAST(course.version, nodes)


def compile_probe_plan(ast: CurriculumAST, *, variants_per_axis: int = 4):
    """Reusable factorized probe design, separate from admission and golds.

    Cross product over truth, universe cardinality and seeded world/query
    identities. Future AST node families must attach their own typed,
    independently verified construction operators rather than fake answers.
    """
    if variants_per_axis < 2:
        raise ValueError("CURRICULUM_PROBE_TOO_NARROW_VARIATION")
    rows = []
    for node in ast.nodes:
        if node.grade != "A" or node.id not in {
                "A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS"}:
            raise ValueError("CURRICULUM_NO_SOURCE_ATTESTED_PROBE_BUILDER:" + node.id)
        if node.requires or node.composed_of or node.answers != ("binary",):
            raise ValueError("CURRICULUM_UNSUPPORTED_NODE_STRUCTURE:" + node.id)
        for size in (3, 4):
            for truth in (False, True):
                for variant in range(variants_per_axis):
                    identity = (node.id, size, truth, variant)
                    rows.append({"capability": node.id, "world_size": size,
                                 "positive": truth, "variant": variant,
                                 "probe_id": hashlib.sha256(json.dumps(identity).encode()).hexdigest(),
                                 "builder": "bilqis_mlx.grade_a_probe.make_record",
                                 "oracle": node.oracle})
    return tuple(rows)


def diagnose_coverage(ast: CurriculumAST, plans):
    """Check factor coverage, independent of model performance or exam gold."""
    findings = []
    for node in ast.nodes:
        rows = [r for r in plans if r["capability"] == node.id]
        groups = {(r["world_size"], r["positive"]) for r in rows}
        expected = {(size, truth) for size in (3, 4) for truth in (False, True)}
        if groups != expected:
            findings.append({"capability": node.id, "failure": "MISSING_FACTOR_CONTRAST"})
        if any(len({r["variant"] for r in rows if (r["world_size"], r["positive"]) == group}) < 2
               for group in expected):
            findings.append({"capability": node.id, "failure": "SINGLE_WORLD_IDENTITY"})
    return tuple(findings)


def materialize_probes(plans, *, micro, development, graph, excluded_record_ids=()):
    """Actually compile legal source records with three agreeing gold oracles.

    This is a candidate-only generator. No sealed exam, optimizer, or
    user-accepted lesson inventory is modified.
    """
    from .grade_a_probe import make_record
    from .grade_a_oracle import evaluate as independent_oracle
    output = []
    identities = set(excluded_record_ids)
    for plan in plans:
        seed = int(plan["probe_id"][:16], 16)
        rng = random.Random(seed)
        for _ in range(300):
            record, library = make_record(
                plan["capability"], rng, plan["positive"], split="train",
                micro=micro, development=development, universe_size=plan["world_size"])
            identity = hashlib.sha256(json.dumps(record, sort_keys=True,
                                separators=(",", ":")).encode()).hexdigest()
            if identity not in identities:
                break
        else:
            raise ValueError("CURRICULUM_PROBE_DISTINCT_WORLD_EXHAUSTED")
        gold = library.evaluate(record)
        if (gold != library.independent_evaluate(record) or
                gold != independent_oracle(record, plan["capability"]) or
                (gold == "TRUE") != plan["positive"]):
            raise ValueError("CURRICULUM_PROBE_ORACLES_DISAGREE")
        tokens = list(library.encode(record))
        if not tokens or len(tokens) > 96 or min(tokens) < 0 or max(tokens) >= len(graph["tokens"]):
            raise ValueError("CURRICULUM_PROBE_OUTSIDE_APPROVED_VOCABULARY")
        identities.add(identity)
        output.append({**plan, "record_id": identity, "record": record,
                       "tokens": tokens, "gold": gold, "admitted": False})
    return tuple(output)
