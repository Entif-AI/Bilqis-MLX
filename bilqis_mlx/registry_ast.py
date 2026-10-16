"""Typed, read-only projection of the native Bilqis Curriculum Registry.

The spreadsheet is a living editorial ledger, not a training admission API.
Only the separately approved Course + source/assessment seals can authorize
teaching; this compiler can enumerate and order *proposed* constructions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import re

from .curriculum_compiler import CurriculumAST
from .semantics.abi import HISTORICAL_PREFIX_SIZE
from .token_atlas import ORIGINAL_GRAPH_DIGEST


SCHEMA = "bilqis.curriculum.registry-snapshot/v1"
SOURCE_ID = "1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so"
LESSON_ID = re.compile(r"LESSON-\d{3}")
GRADE_ID = re.compile(r"[A-Z]")
REQUIRED_HEADERS = {
    "Lessons": ("Legacy ID", "Proposed neutral Lesson ID", "Legacy domain",
                "Historical title", "What the lesson represents",
                "Present teaching / scope", "Prerequisite roots to establish",
                "Current assessment criterion", "Evidence status",
                "Naming issue / gate", "Source path",
                "Verified run PR / immutable release URL"),
    "Prerequisites": ("Sequence", "New concept / capability", "Earlier mastered root",
                      "Construction teaching required", "Allowed assessment",
                      "Status / decision", "Source", "Candidate Grade",
                      "Proposed Lesson ID", "Required Earlier Grade(s)",
                      "Required Earlier Lesson (within grade)", "Admission evidence gate"),
    "Grade Tranches": ("Grade/tranche ID", "Provisional subject family",
                       "Relationship to previous grade", "Capabilities that belong here",
                       "Referential construction evidence", "Qualifying metric roster",
                       "Independent teacher vote", "Status",
                       "Version(s) used for provenance", "Notes",
                       "GitHub Issue (proposed grade)", "Official grammar coverage"),
    "Token Atlas": ("0-based Token ID", "Bilqis token symbol", "Pasigraphy identity",
                    "Source-grounded semantic role/function", "Formal signature",
                    "Semantic family", "Source subtype", "NI bridge or grammar locus",
                    "Lesson provenance", "Token mastery evidence", "Meaning-review status",
                    "Arity", "Source stage", "Node contract SHA-256",
                    "Source graph SHA-256", "Historical source / notes"),
    "Semantic Bridges": ("Bridge ID", "Source locus / era", "Ithkuil category / root",
                         "Source-grounded semantic meaning", "Link type",
                         "Prior Bilqis concepts (NOT asserted mastered)",
                         "Proposed constructive exercise / varied context",
                         "Assessment / retention probe (PROPOSED)",
                         "Registry links / reserved lesson", "Status / gate",
                         "Primary source", "Semantic caution / dependencies"),
}


@dataclass(frozen=True)
class Origin:
    tab: str
    row: int
    sheet_id: int


@dataclass(frozen=True)
class TokenNode:
    id: int
    symbol: str
    identity: str
    meaning: str
    signature: str
    family: str
    subtype: str
    arity: str
    ni_locus: str
    graph_sha256: str
    contract_sha256: str
    meaning_review: str
    origin: Origin


@dataclass(frozen=True)
class LessonNode:
    id: str
    legacy_alias: str
    title: str
    semantics: str
    teaching_intent: str
    prerequisite_text: str
    assessment_intent: str
    evidence_status: str
    gate: str
    source_claim: str
    grade: str | None
    requires_grades: tuple[str, ...]
    requires_lessons: tuple[str, ...]
    construction: str
    intended_probe: str
    origin: Origin


@dataclass(frozen=True)
class PrerequisiteNode:
    sequence: str
    concept: str
    prerequisite_text: str
    construction: str
    assessment: str
    status: str
    source_claim: str
    grade: str
    proposed_lesson: str
    requires_grades: tuple[str, ...]
    requires_lessons: tuple[str, ...]
    evidence_gate: str
    origin: Origin


@dataclass(frozen=True)
class GradeNode:
    id: str
    title: str
    status: str
    planned_capabilities: str
    notes: str
    origin: Origin


@dataclass(frozen=True)
class BridgeNode:
    id: str
    concept: str
    meaning: str
    link_type: str
    construction: str
    probe: str
    status: str
    source_claim: str
    caution: str
    related_lessons: tuple[str, ...]
    origin: Origin


@dataclass(frozen=True)
class RegistryAST:
    source_id: str
    source_sha256: str
    tokens: tuple[TokenNode, ...]
    lessons: tuple[LessonNode, ...]
    prerequisites: tuple[PrerequisiteNode, ...]
    grades: tuple[GradeNode, ...]
    bridges: tuple[BridgeNode, ...]
    supplemental_constraints: tuple[PrerequisiteNode, ...]
    training_authorized: bool = False

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class StagePlan:
    grade: str
    status: str
    lessons: tuple[LessonNode, ...]
    blockers: tuple[str, ...]
    training_authorized: bool = False

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class ConstructionTask:
    id: str
    concept: str
    instruction: str
    proposed_probe: str
    unmet_grades: tuple[str, ...]
    unmet_lessons: tuple[str, ...]
    ready_to_construct: bool
    training_authorized: bool = False


def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _text(row: list, i: int) -> str:
    return str(row[i]).strip() if i < len(row) and row[i] is not None else ""


def _grade_refs(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    grades = tuple(s for s in re.split(r"[,;\s]+", value) if s)
    if not grades or any(not GRADE_ID.fullmatch(g) for g in grades):
        raise ValueError("REGISTRY_UNRESOLVED_GRADE_REFERENCE:" + value)
    if len(set(grades)) != len(grades):
        raise ValueError("REGISTRY_DUPLICATE_GRADE_REFERENCE")
    return grades


def _table(snapshot: dict, tab: str):
    entry = snapshot.get("tabs", {}).get(tab)
    if not isinstance(entry, dict) or not isinstance(entry.get("rows"), list):
        raise ValueError("REGISTRY_REQUIRED_TAB_MISSING:" + tab)
    rows = entry["rows"]
    head = REQUIRED_HEADERS[tab]
    if not rows or tuple(rows[0]) != head:
        raise ValueError("REGISTRY_HEADER_DRIFT:" + tab)
    if not isinstance(entry.get("sheet_id"), int):
        raise ValueError("REGISTRY_SHEET_ID_MISSING:" + tab)
    return rows[1:], entry["sheet_id"]


def _origin(tab: str, i: int, sheet_id: int) -> Origin:
    return Origin(tab, i, sheet_id)


def parse_registry(snapshot: dict) -> RegistryAST:
    """Compile exact bounded Sheet rows without inferring any admission state."""
    if (snapshot.get("schema") != SCHEMA or
            snapshot.get("source", {}).get("spreadsheet_id") != SOURCE_ID or
            snapshot["source"].get("read_policy") != "read-only"):
        raise ValueError("REGISTRY_SNAPSHOT_IDENTITY_OR_SCHEMA_DRIFT")

    rows, sheet = _table(snapshot, "Token Atlas")
    tokens = tuple(TokenNode(int(_text(r, 0)), _text(r, 1), _text(r, 2),
                             _text(r, 3), _text(r, 4), _text(r, 5),
                             _text(r, 6), _text(r, 11), _text(r, 7),
                             _text(r, 14), _text(r, 13), _text(r, 10),
                             _origin("Token Atlas", i, sheet))
                   for i, r in enumerate(rows, 2))
    if len({t.identity for t in tokens}) != len(tokens) or not all(t.identity for t in tokens):
        raise ValueError("REGISTRY_DUPLICATE_TOKEN_IDENTITY")
    if len({t.symbol for t in tokens}) != len(tokens):
        raise ValueError("REGISTRY_DUPLICATE_TOKEN_SYMBOL")
    if (len(tokens) != HISTORICAL_PREFIX_SIZE or
            tuple(t.id for t in tokens) != tuple(range(HISTORICAL_PREFIX_SIZE))
            or any(t.graph_sha256 != ORIGINAL_GRAPH_DIGEST for t in tokens)):
        raise ValueError("REGISTRY_PINNED_222_TOKEN_GRAPH_DRIFT")
    if any(t.identity != "legacy:" + t.symbol or not t.signature or not t.meaning or
           len(t.contract_sha256) != 64 for t in tokens):
        raise ValueError("REGISTRY_TOKEN_IDENTITY_DRIFT")

    rows, sheet = _table(snapshot, "Lessons")
    original_lessons = []
    for i, row in enumerate(rows, 2):
        ident = _text(row, 1)
        if not LESSON_ID.fullmatch(ident):
            raise ValueError("REGISTRY_LESSON_ID_INVALID:" + ident)
        original_lessons.append(LessonNode(
            ident, _text(row, 0), _text(row, 3), _text(row, 4),
            _text(row, 5), _text(row, 6), _text(row, 7), _text(row, 8),
            _text(row, 9), _text(row, 10), None, (), (), "", "",
            _origin("Lessons", i, sheet)))
    ids = [l.id for l in original_lessons]
    if len(ids) != len(set(ids)):
        raise ValueError("REGISTRY_DUPLICATE_LESSON_ID")
    lesson_by_id = {x.id: x for x in original_lessons}

    rows, sheet = _table(snapshot, "Prerequisites")
    prereqs = []
    supplemental = []
    linked = {}
    for i, row in enumerate(rows, 2):
        raw_lesson, grade = _text(row, 8), _text(row, 7)
        structured = bool(LESSON_ID.fullmatch(raw_lesson) and GRADE_ID.fullmatch(grade))
        grades = _grade_refs(_text(row, 9)) if structured else ()
        earlier = _text(row, 10)
        references = (earlier,) if structured and earlier else ()
        node = PrerequisiteNode(
            _text(row, 0), _text(row, 1), _text(row, 2), _text(row, 3),
            _text(row, 4), _text(row, 5), _text(row, 6), grade, raw_lesson, grades,
            references, _text(row, 11), _origin("Prerequisites", i, sheet))
        if structured and raw_lesson not in linked:
            if raw_lesson not in lesson_by_id:
                raise ValueError("REGISTRY_UNRESOLVED_LESSON_REFERENCE:" + raw_lesson)
            linked[raw_lesson] = node
            prereqs.append(node)
        else:
            # Unstructured annotations (including the late J qualification
            # amendments) are preserved, never converted to runnable edges.
            supplemental.append(node)

    ranked = {k: i for i, k in enumerate(linked)}
    for name, item in linked.items():
        for parent in item.requires_lessons:
            if parent not in linked:
                raise ValueError("REGISTRY_UNRESOLVED_LESSON_REFERENCE:" + parent)
            if (ranked[parent] >= ranked[name] or linked[parent].grade != item.grade):
                raise ValueError("REGISTRY_FORWARD_OR_CYCLIC_LESSON_DEPENDENCY:" + name)
    for name, item in linked.items():
        if item.grade in item.requires_grades:
            raise ValueError("REGISTRY_SELF_PREREQUISITE_GRADE:" + item.grade)
    lessons = tuple(replace(x, grade=linked[x.id].grade,
                            requires_grades=linked[x.id].requires_grades,
                            requires_lessons=linked[x.id].requires_lessons,
                            construction=linked[x.id].construction,
                            intended_probe=linked[x.id].assessment)
                    if x.id in linked else x for x in original_lessons)

    rows, sheet = _table(snapshot, "Grade Tranches")
    grades = tuple(GradeNode(_text(r, 0), _text(r, 1), _text(r, 7),
                             _text(r, 3), _text(r, 9),
                             _origin("Grade Tranches", i, sheet))
                   for i, r in enumerate(rows, 2))
    if len({g.id for g in grades}) != len(grades):
        raise ValueError("REGISTRY_DUPLICATE_GRADE_ID")
    grade_ids = {g.id for g in grades}
    if any(node.grade not in grade_ids or any(g not in grade_ids for g in node.requires_grades)
           for node in linked.values()):
        raise ValueError("REGISTRY_UNRESOLVED_GRADE_REFERENCE")

    rows, sheet = _table(snapshot, "Semantic Bridges")
    bridges = tuple(BridgeNode(
        _text(r, 0), _text(r, 2), _text(r, 3), _text(r, 4),
        _text(r, 6), _text(r, 7), _text(r, 9), _text(r, 10),
        _text(r, 11), tuple(dict.fromkeys(LESSON_ID.findall(_text(r, 8)))),
        _origin("Semantic Bridges", i, sheet))
        for i, r in enumerate(rows, 2))
    if len({b.id for b in bridges}) != len(bridges) or any(not b.id for b in bridges):
        raise ValueError("REGISTRY_DUPLICATE_SEMANTIC_BRIDGE_ID")

    return RegistryAST(SOURCE_ID, _digest(snapshot), tokens, lessons,
                       tuple(prereqs), grades, bridges, tuple(supplemental))


def load_registry(path: Path) -> RegistryAST:
    return parse_registry(json.loads(Path(path).read_text(encoding="utf-8")))


def bind_course_tokens(course: CurriculumAST, registry: RegistryAST) -> dict[str, tuple[int, ...]]:
    """Fail closed unless every currently taught root binds to a known token."""
    index = {token.symbol: token for token in registry.tokens}
    result = {}
    for cap in course.nodes:
        if any(root not in index for root in cap.roots):
            raise ValueError("REGISTRY_ADMITTED_COURSE_HAS_UNKNOWN_TOKEN:" + cap.id)
        result[cap.id] = tuple(index[root].id for root in cap.roots)
    return result


def stage_plan(registry: RegistryAST, grade: str) -> StagePlan:
    """Topological authoring plan, not approval to train the proposed stage."""
    found = next((g for g in registry.grades if g.id == grade), None)
    if found is None:
        raise ValueError("REGISTRY_UNKNOWN_PROPOSED_GRADE:" + grade)
    rank = {p.proposed_lesson: i for i, p in enumerate(registry.prerequisites)}
    members = tuple(sorted((x for x in registry.lessons if x.grade == grade),
                           key=lambda item: rank[item.id]))
    requires = tuple(dict.fromkeys(g for lesson in members
                                   for g in lesson.requires_grades))
    blockers = ["REGISTRY_PROPOSAL_NOT_NEURAL_TRAINING_RELEASE"]
    if "HISTORICAL" in found.status or "CONTINUITY" in found.status:
        blockers.append("HISTORICAL_GRADE_ALIAS_NOT_EXECUTABLE")
    if requires:
        blockers.append("REQUIRES_EARLIER_GRADES:" + ",".join(requires))
    if not members:
        blockers.append("NO_STRUCTURED_ADMITTED_LESSON_MEMBERS")
    annotations = [note for note in registry.supplemental_constraints
                   if grade in re.split(r"[^A-Z]+", note.grade)]
    if annotations:
        blockers.append("ADDITIONAL_UNCOMPILED_QUALIFICATION_CONSTRAINTS:" +
                        str(len(annotations)))
    return StagePlan(grade, found.status, members, tuple(blockers))


def construction_frontier(plan: StagePlan, *, mastered_grades=(),
                          constructed_lessons=()) -> tuple[ConstructionTask, ...]:
    """Deterministically discover the next eligible *authoring* tasks.

    Completed grades/lessons must be independently evidenced by the caller.
    An eligible task is NOT a semantic certification, exam or optimizer update.
    """
    mastered = set(mastered_grades)
    constructed = set(constructed_lessons)
    valid = {item.id for item in plan.lessons}
    if constructed - valid:
        raise ValueError("REGISTRY_UNKNOWN_CONSTRUCTED_LESSON:" + ",".join(sorted(constructed - valid)))
    unresolved_qualification = any(
        "UNCOMPILED_QUALIFICATION_CONSTRAINTS" in blocker
        for blocker in plan.blockers)
    tasks = []
    for item in plan.lessons:
        if item.id in constructed:
            continue
        missing_grades = tuple(g for g in item.requires_grades if g not in mastered)
        missing_lessons = tuple(l for l in item.requires_lessons if l not in constructed)
        tasks.append(ConstructionTask(item.id, item.semantics, item.construction,
                                      item.intended_probe, missing_grades,
                                      missing_lessons,
                                      not missing_grades and not missing_lessons and
                                      not unresolved_qualification))
    return tuple(tasks)


def compiler_report(snapshot: Path, *, grade: str = "C",
                    assumed_mastered_grades=(), constructed_lessons=()) -> dict:
    """Produce a reproducible proposed teaching frontier, never optimizer work."""
    from .curriculum_compiler import compile_ast, compile_probe_plan
    from .grade_a_release import accepted_grade_a

    registry = load_registry(snapshot)
    manifest = json.loads((Path(__file__).resolve().parents[1] /
                           "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
    active = compile_ast(accepted_grade_a(manifest))
    bound = bind_course_tokens(active, registry)
    stage = stage_plan(registry, grade)
    tasks = construction_frontier(stage,
                                  mastered_grades=assumed_mastered_grades,
                                  constructed_lessons=constructed_lessons)
    return {
        "schema": "bilqis.mlx.registry-curriculum-plan/v1",
        "source_spreadsheet_id": registry.source_id,
        "source_snapshot_sha256": registry.source_sha256,
        "compiled_registry_ast_sha256": registry.digest(),
        "registered_semantic_tokens": len(registry.tokens),
        "historic_legacy_lessons": len(registry.lessons),
        "recorded_prerequisite_rows": len(registry.prerequisites) + len(registry.supplemental_constraints),
        "semantic_bridge_research_proposals": len(registry.bridges),
        "current_active_grade_a_course": active.version,
        "active_grade_a_token_binding": bound,
        "unreleased_grade_a_source_probe_plans": len(compile_probe_plan(active)),
        "proposed_stage": grade,
        "proposed_stage_status": stage.status,
        "proposed_stage_plan_sha256": stage.digest(),
        "proposed_stage_blockers": stage.blockers,
        "hypothetical_prerequisites_only": True,
        "assumed_mastered_grades": tuple(assumed_mastered_grades),
        "proposed_construction_tasks": [asdict(t) for t in tasks],
        "generated_exercises_admitted": 0,
        "training_authorized_by_this_report": False,
        "neural_optimizer_updates": 0,
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Neural-inert Registry AST construction planning")
    parser.add_argument("--snapshot", type=Path, default=(
        Path(__file__).resolve().parents[1] / "docs/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json"))
    parser.add_argument("--grade", default="C")
    parser.add_argument("--assume-mastered", nargs="*", default=(),
                        help="WHAT-IF grade assumptions only, never mastery/admission receipts")
    parser.add_argument("--constructed", nargs="*", default=(),
                        help="WHAT-IF prior construction IDs, not proof of examination mastery")
    args = parser.parse_args(argv)
    print(json.dumps(compiler_report(args.snapshot, grade=args.grade,
        assumed_mastered_grades=args.assume_mastered,
        constructed_lessons=args.constructed), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
