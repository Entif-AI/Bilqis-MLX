"""Registry LESSON-058..062: staged, source-checked concrete number teaching.

This release is a scoped formal adapter, with no claim of NI wordform legality.
Actual C admission is a human-operated successor transition after A+B mastery.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .curriculum import AnswerFamily, BINARY, Capability, Grade
from .generated_assessment import digest
from .integer_curriculum import IntegerScope
from .numeric_curriculum import GENERATOR, ORACLE, NumericLesson, draw_numeric
from .semantics.numeric import CONTRACT, CONTRACT_PATH
from .token_atlas import COLUMNS, rows_for_graph
from .vocabulary_growth import AdmittedToken, append_catalog

RELEASE = "bilqis.mlx.grade-a-b-c-live/20261016-v1"
REGISTRY_PATH = Path(__file__).resolve().parent / "semantics/numeric_registry_v1.json"
REGISTRY_COUNTING_TARGET = 10
PLANS = (
    NumericLesson("C.COUNT", "LESSON-058", "COUNT", ("A.IDENTITY", "A.MEMBER")),
    NumericLesson("C.NUMBER", "LESSON-059", "NUMBER", ("C.COUNT",)),
    NumericLesson("C.SUCCESSOR", "LESSON-058", "SUCC", ("C.COUNT", "C.NUMBER")),
    NumericLesson("C.ADD", "LESSON-060", "ADD", ("C.COUNT", "C.NUMBER", "C.SUCCESSOR")),
    NumericLesson("C.SUB", "LESSON-060", "SUB", ("C.COUNT", "C.NUMBER", "C.ADD")),
    NumericLesson("C.MUL", "LESSON-061", "MUL", ("C.COUNT", "C.NUMBER", "C.ADD")),
    NumericLesson("C.DIV", "LESSON-062", "DIV", ("C.COUNT", "C.NUMBER", "C.MUL")),
)


def constructor_digest():
    root = Path(__file__).resolve().parent
    files = ("live_grade_c.py", "numeric_curriculum.py", "semantics/numeric.py",
             "semantics/numeric_v1.json", "source_adapters/numeric.py", "verification/numeric.py")
    import hashlib
    return digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files})


def admissions():
    authority = "user:2026-10-16/full-registry-grade-c-staged-prerequisite-mastery"
    proof = digest({"contract": CONTRACT, "implementation": constructor_digest(), "authority": authority})
    result = []
    for node in CONTRACT["append_only_nodes"]:
        result.append(AdmittedToken(
            token_id=node["id"], semantic_id=node["semantic_id"], meaning=node["meaning"],
            source_kind="mathematics", representation="compositional",
            source_locator=CONTRACT["sources"][0], source_digest=digest(CONTRACT),
            lesson_digest=digest([p.__dict__ for p in PLANS]), oracle_digest=proof,
            prerequisite_tokens=("school.number.0", "school.number.1"),
            capability_id=next(p.capability for p in PLANS if p.lesson_id == node["lesson_id"]),
            admission_receipt=proof, signature=node["signature"], arity=node["arity"]))
    return tuple(result)


def proposed_graph(parent: dict):
    """Neural-inert proposal for source checks and native Registry staging only."""
    return append_catalog(parent, admissions(), allow_disposable_fixtures=True)[0]


def expanded_graph(parent: dict):
    evidence = json.loads(REGISTRY_PATH.read_text())
    expected = {entry.admission_receipt for entry in admissions()}
    if (evidence.get("release") != RELEASE or evidence.get("admission_receipts") != sorted(expected) or
            evidence.get("native_rows_sha256") != digest(evidence.get("rows")) or
            evidence.get("spreadsheet_id") != "1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so"):
        raise ValueError("GRADE_C_NATIVE_REGISTRY_ADMISSION_NOT_VERIFIED")
    graph, _ = append_catalog(parent, admissions(),
        canonical_registry_rows=evidence["rows"], approved_ledger_version=RELEASE,
        approved_admissions=tuple(sorted(expected)))
    return graph


def registry_graph():
    """Load the checked native projection; actual-model admission is separate."""
    evidence = json.loads(REGISTRY_PATH.read_text())
    graph = evidence["graph"]
    from .semantics.abi import HISTORICAL_ABI, HISTORICAL_PREFIX_SIZE, fingerprint_graph_prefix
    if fingerprint_graph_prefix(graph) != HISTORICAL_ABI.index_contract_sha256:
        raise ValueError("GRADE_C_HISTORICAL_PREFIX_DRIFT")
    parent = {**graph, "tokens": graph["tokens"][:HISTORICAL_PREFIX_SIZE],
              "nodes": graph["nodes"][:HISTORICAL_PREFIX_SIZE],
              "row_contract_sha256": {key: graph["row_contract_sha256"][key]
                                       for key in graph["tokens"][:HISTORICAL_PREFIX_SIZE]}}
    if expanded_graph(parent) != graph:
        raise ValueError("GRADE_C_REGISTERED_GRAPH_DRIFT")
    return graph


def prepare_course(previous, *, maximum=None):
    graph = registry_graph()
    maximum = integer_scope(graph) if maximum is None else maximum
    if maximum != REGISTRY_COUNTING_TARGET:
        raise ValueError("GRADE_C_FULL_REGISTRY_REQUIRES_BILQIS_INTEGER_MAX=" + str(REGISTRY_COUNTING_TARGET))
    return live_course(previous, graph, maximum=maximum), graph


def integer_scope(graph):
    parity = {"heads": {"semantic_token": {"values": graph["tokens"]},
              "numeric_full_101": {"values": [str(i) for i in range(101)]}}}
    return IntegerScope.from_environment(parity).maximum


def items_per_capability(maximum):
    return max(12, 3*(maximum+1))


def draw(graph, *, seed, maximum, each=None, capability=None):
    return draw_numeric(PLANS, graph, seed=seed, maximum=maximum,
        each=items_per_capability(maximum) if each is None else each, capability=capability)


def live_course(previous, graph, *, maximum):
    if len(previous.grades) != 2 or tuple(g.id for g in previous.grades) != ("A", "B"):
        raise ValueError("GRADE_C_REQUIRES_UNCHANGED_A_B_RELEASE")
    if type(maximum) is not int or not 1 <= maximum <= 10:
        raise ValueError("GRADE_C_INTEGER_SCOPE_INVALID")
    witness = draw(graph, seed=20261016, maximum=maximum)
    per_cap = items_per_capability(maximum)
    seal = digest({"previous": previous.digest(), "generator": constructor_digest(),
                   "graph": digest(graph), "scope": maximum, "witness": witness})
    roots = lambda p: (tuple("school.number."+str(i) for i in range(maximum+1))
                       if p.operation == "NUMBER" else ("school.op."+p.operation,))
    caps = tuple(Capability(id=p.capability, difficulty="grounded-finite-numbers",
        source_anchor=CONTRACT["sources"][0],
        taught_roots=roots(p), examined_roots=roots(p), prerequisites=p.prerequisites,
        composed_of=(), answer_families=(AnswerFamily("binary", BINARY),
            AnswerFamily("numeric_active", tuple(str(i) for i in range(maximum+1)))),
        lesson_generator="bilqis_mlx.numeric_curriculum.draw_numeric",
        independent_oracle=ORACLE) for p in PLANS)
    grade = Grade("C", caps, assessment_sha256=seal,
        exam_item_counts=tuple((c.id, per_cap) for c in caps),
        teaching_stages=tuple((c.id,) for c in caps))
    return replace(previous, grades=(*previous.grades, grade), version=RELEASE,
        source_attestation_sha256=digest({"previous": previous.source_attestation_sha256,
                                          "numeric": CONTRACT, "graph": digest(graph)}),
        assessment_manifest_sha256=seal)


def answer_heads(graph, maximum):
    names = list(graph["tokens"])
    return {"semantic_token": {"values": names, "token_ids": list(range(len(names)))},
            "numeric_active": {"values": [str(i) for i in range(maximum+1)],
                "token_ids": [names.index("school.number."+str(i)) for i in range(maximum+1)]},
            "binary": {"values": ["FALSE", "TRUE"],
                "token_ids": [names.index("cogal.value.false"), names.index("cogal.value.true")]}}
