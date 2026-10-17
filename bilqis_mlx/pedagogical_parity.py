"""Read-only teaching contract recovered from School50 v10, not a new grade.

The frozen Grade A course is untouched. Source-grounded numeric constructions,
true/false assertions, and counterexamples share one underlying arithmetic
expression. Acquisition replay deliberately repeats *taught* questions;
development and sealed source expressions remain reserved and are not used for
candidate selection. No training, qualification, or admission occurs here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path

from .backup import digest_file
from .grade_a_probe import PINNED_FULL_STUDENT_GRAPH_SHA256, read_sources
from .source import AUDITED_PARENT
from .semantics.abi import HISTORICAL_PREFIX_SIZE


SCHEMA = "bilqis.mlx.predecessor-pedagogy/v2"
PREDECESSOR = {
    "bilqis_school/small_domain_lessons.py":
        "44c73637ed9bcfb6316446937cdc318d911f6178c07fd929ac6222014c83f6e5",
    "bilqis_school/arithmetic.py":
        "b6477344cac66e0f4311ce798b9d4265a315452447e7643664765de6eaef8f40",
    "bilqis_school/numeric_answer_contract.py":
        "23db30c2ce938681c32dc823265c1bb9b64daecdc5fd41975e032e21d038190d",
    "bilqis_school/lessons.py":
        "22b3b712e48322d68aec1ee525327f64554b8a00b8a1e7c54e416ebd1516a4c7",
    "bilqis_school/spiral_semantic_bridge.py":
        "842789f0e010d7139f283b91993325d276cdda38ccf205d4823be280d794abe9",
    "bilqis_school/spiral_staged_runner.py":
        "e815f46b04b3e8dc94b9521adacf0201b38e782955d2d15c4d95656eb2f9b7dc",
    "bilqis_school/engine.py":
        "6b62f288750bc6d129b349e0333b560f480ede900bf28e3b641299fe696abaa1",
}
STAGE_ORDER = ("NUMERAL_IDENTITY", "DIRECT_ARITHMETIC", "TRUTH_CONTRAST")
REQUIRES = {
    "NUMERAL_IDENTITY": (),
    "DIRECT_ARITHMETIC": ("NUMERAL_IDENTITY",),
    "TRUTH_CONTRAST": ("NUMERAL_IDENTITY", "DIRECT_ARITHMETIC"),
}


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                    ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _source_stack(root: Path):
    root = Path(root).resolve(strict=True)
    actual = {}
    for name, expected in PREDECESSOR.items():
        path = root / name
        actual[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual[name] != expected:
            raise ValueError("PARITY_PREDECESSOR_SOURCE_DRIFT:" + name)
    _, _, earlier_graph, other_sources, earlier_sha = read_sources(root)
    source = importlib.import_module("bilqis_school.small_domain_lessons")
    arithmetic = importlib.import_module("bilqis_school.arithmetic")
    numbers = importlib.import_module("bilqis_school.numeric_answer_contract")
    micro = importlib.import_module("bilqis_micro.graph")
    for module, relative in ((source, "bilqis_school/small_domain_lessons.py"),
                             (arithmetic, "bilqis_school/arithmetic.py"),
                             (numbers, "bilqis_school/numeric_answer_contract.py")):
        if Path(module.__file__).resolve() != root / relative:
            raise ValueError("PARITY_IMPORTED_PREDECESSOR_WRONG_ROOT")
    # The *historical parent* retains its immutable original token prefix.
    # The active student can subsequently grow beyond that prefix. Rebuilding
    # the parent from source changes its node-contract hash, so load the
    # pinned frozen original rather than treating reconstruction as parity.
    original = (root / "runs/primitive-consolidation-v16-triplets" /
                AUDITED_PARENT.basename)
    if digest_file(original) != AUDITED_PARENT.sha256:
        raise ValueError("PARITY_ORIGINAL_STUDENT_SHA_DRIFT")
    import torch
    payload = torch.load(original, map_location="cpu", weights_only=True)
    graph = payload["graph"]
    graph_sha = _digest(graph)
    if (graph_sha != PINNED_FULL_STUDENT_GRAPH_SHA256 or
            graph["tokens"][:len(earlier_graph["tokens"])] != earlier_graph["tokens"] or
            len(graph["tokens"]) != HISTORICAL_PREFIX_SIZE):
        raise ValueError("PARITY_PINNED_FULL_STUDENT_GRAPH_DRIFT")
    full = dict(actual, **other_sources)
    return source, arithmetic, numbers, micro, graph, _digest({
        "source_files": full, "base_graph_sha256": earlier_sha,
        "full_graph_sha256": graph_sha, "checkpoint_sha256": AUDITED_PARENT.sha256})


def _answer_heads(graph, numbers, micro):
    vocab = {token: i for i, token in enumerate(graph["tokens"])}
    if len(vocab) != len(graph["tokens"]):
        raise ValueError("PARITY_DUPLICATED_GRAPH_IDENTITY")
    all_numbers = list(numbers.numeric_token_ids(graph))
    evidence_ids = [vocab["cogal.value.false"], vocab["cogal.value.true"]]
    evidence_ids.extend(vocab["micro.state." + state] for state in micro.STATES[2:])
    if evidence_ids[:2] != [6, 7] or len(set(evidence_ids)) != 5:
        raise ValueError("PARITY_NATIVE_EVIDENCE_HEAD_DRIFT")
    return {
        "semantic_token": {"values": list(graph["tokens"]),
                           "token_ids": list(range(len(graph["tokens"])))},
        "numeric_0_3": {"values": [str(i) for i in range(4)],
                         "token_ids": all_numbers[:4]},
        "numeric_full_101": {"values": [str(i) for i in range(101)],
                             "token_ids": all_numbers},
        "evidence": {"values": list(micro.STATES), "token_ids": evidence_ids},
    }


def _row(arithmetic, mapping, expression, *, source_id, source,
         partition, kind, expected):
    arithmetic.verify(expression)
    value = arithmetic.evaluate(expression)
    actual = ("TRUE" if value else "FALSE") if type(value) is bool else str(value)
    if expected != actual:
        raise ValueError("PARITY_GOLD_NOT_ORACLE_EVALUATION")
    record = {"task": arithmetic.VERSION, "expression": deepcopy(expression)}
    ids = arithmetic.encode(record, mapping)
    if (not ids or len(ids) > 96 or
            any(type(i) is not int or i < 0 or i >= len(mapping) for i in ids)):
        raise ValueError("PARITY_UNKNOWN_SOURCE_TOKEN_OR_CONTEXT")
    native = _native_output(kind, expected, mapping)
    return {"id": _digest(record), "source_id": source_id,
            "source": list(source), "partition": partition,
            "answer_kind": kind, "gold": expected,
            **({"native_output": native} if native else {}),
            "record": record, "tokens": ids,
            "oracle": "bilqis_school.arithmetic.evaluate+independent_evaluate"}


def _native_output(kind: str, gold: str, mapping: dict[str, int]):
    """Bind an oracle-checked number answer to its full-catalog token ID."""
    if kind != "numeric_0_3":
        return None
    identity = "school.number." + gold
    if gold not in ("0", "1", "2", "3") or identity not in mapping:
        raise ValueError("PARITY_DIRECT_NUMBER_NOT_IN_MODEL_SEMANTIC_ABI")
    return {"identity": identity, "token_id": mapping[identity]}


def _pair(source, arithmetic, mapping, assignment, partition):
    expr = source.expression(assignment)
    actual = arithmetic.evaluate(expr)
    if (type(actual) is not int or actual not in range(4) or
            assignment not in source.SOURCES[partition]):
        raise ValueError("PARITY_UNBOUNDED_OR_UNOWNED_ARITHMETIC")
    owner = source._source_id(expr)
    positive = source._eq(expr, actual)
    negative = source._eq(expr, source._wrong(actual))
    rows = [
        _row(arithmetic, mapping, expr, source_id=owner, source=assignment,
             partition=partition, kind="numeric_0_3", expected=str(actual)),
        _row(arithmetic, mapping, positive, source_id=owner, source=assignment,
             partition=partition, kind="evidence", expected="TRUE"),
        _row(arithmetic, mapping, negative, source_id=owner, source=assignment,
             partition=partition, kind="evidence", expected="FALSE"),
    ]
    if len({row["id"] for row in rows}) != 3:
        raise ValueError("PARITY_COLLIDING_ANSWER_VIEWS")
    return {"source": list(assignment), "source_id": owner,
            "value": actual, "partition": partition, "rows": rows}


def _build(root: Path):
    source, arithmetic, numbers, micro, graph, source_sha = _source_stack(root)
    mapping = {name: i for i, name in enumerate(graph["tokens"])}
    heads = _answer_heads(graph, numbers, micro)
    if ({k: len(v) for k, v in source.SOURCES.items()} !=
            {"train": 12, "development": 4, "sealed": 4} or
            len(source.REPLAY_SOURCES) != 4 or
            any(s not in source.SOURCES["train"] for s in source.REPLAY_SOURCES)):
        raise ValueError("PARITY_PREDECESSOR_SOURCE_PARTITIONS_DRIFT")
    pairs = {partition: [_pair(source, arithmetic, mapping, assignment, partition)
                         for assignment in source.SOURCES[partition]]
             for partition in ("train", "development", "sealed")}
    units = [
        _row(arithmetic, mapping, arithmetic.atom(n),
             source_id=_digest(["numeric-identity", n]), source=("NUMERAL", n),
             partition="train", kind="numeric_0_3", expected=str(n))
        for n in range(4)
    ]
    core = set(source.REPLAY_SOURCES)

    def select(partition, index, *, exposed_only=False):
        return [deepcopy(pair["rows"][index])
                for pair in pairs[partition]
                if not exposed_only or tuple(pair["source"]) in core]

    def select_truth(partition, *, exposed_only=False):
        return [deepcopy(row) for pair in pairs[partition]
                if not exposed_only or tuple(pair["source"]) in core
                for row in pair["rows"][1:]]

    stages = {
        "NUMERAL_IDENTITY": {"requires": [], "train": deepcopy(units),
                             "replay": deepcopy(units),
                             "development": [], "sealed": []},
        "DIRECT_ARITHMETIC": {"requires": list(REQUIRES["DIRECT_ARITHMETIC"]),
                              "train": select("train", 0),
                              "replay": select("train", 0, exposed_only=True),
                              "development": select("development", 0),
                              "sealed": select("sealed", 0)},
        "TRUTH_CONTRAST": {"requires": list(REQUIRES["TRUTH_CONTRAST"]),
                           "train": select_truth("train"),
                           "replay": select_truth("train", exposed_only=True),
                           "development": select_truth("development"),
                           "sealed": select_truth("sealed")},
    }
    return {"schema": SCHEMA, "source_sha256": source_sha,
            "predecessor_sha256": dict(PREDECESSOR), "graph_sha256":
                _digest(graph), "heads": heads,
            "core_sources": [list(s) for s in source.REPLAY_SOURCES],
            "pairs": pairs, "stages": stages,
            "training_authorized": False, "qualification_authorized": False,
            "sealed_exam_policy": "RESERVED_NOT_USED_FOR_SELECTION",
            "scope": "RESEARCH_ONLY_PREDECESSOR_PARITY_NOT_A_GRADE_A_REPLACEMENT"}


def build_plan(legacy_root: Path) -> dict:
    """Reconstruct and immediately verify immutable-source lesson semantics."""
    plan = _build(legacy_root)
    _validate_structure(plan)
    return plan


def _validate_structure(plan: dict):
    if (plan.get("training_authorized") is not False or
            plan.get("qualification_authorized") is not False or
            plan.get("sealed_exam_policy") != "RESERVED_NOT_USED_FOR_SELECTION"):
        raise ValueError("PARITY_UNAUTHORIZED_LESSON_OR_EXAM_ADMISSION")
    ids = {}
    for partition, pairs in plan["pairs"].items():
        for pair in pairs:
            source_id = pair["source_id"]
            if source_id in ids:
                raise ValueError("PARITY_SOURCE_PARTITION_LEAK")
            ids[source_id] = partition
            native=pair["rows"][0].get("native_output") if pair["rows"] else None
            heads=plan["heads"]
            expect="school.number."+str(pair["value"])
            if (len(pair["rows"]) != 3 or
                    [r["answer_kind"] for r in pair["rows"]] !=
                    ["numeric_0_3", "evidence", "evidence"] or
                    [r["gold"] for r in pair["rows"]] !=
                    [str(pair["value"]), "TRUE", "FALSE"] or
                    any(r["source_id"] != source_id for r in pair["rows"]) or
                    native != {"identity": expect,
                               "token_id": heads["semantic_token"]["values"].index(expect)}):
                raise ValueError("PARITY_INCOMPLETE_DIRECT_TRUTH_NEGATIVE_PAIR")
    if len(ids) != 20:
        raise ValueError("PARITY_MISSING_PREDECESSOR_EXPRESSIONS")
    for name in STAGE_ORDER:
        stage = plan["stages"][name]
        if stage["requires"] != list(REQUIRES[name]):
            raise ValueError("PARITY_UNTAUGHT_STAGE_PREREQUISITES")
        train = {r["id"] for r in stage["train"]}
        if len(train) != len(stage["train"]):
            raise ValueError("PARITY_COLLIDING_TEACHING_EXAMPLES")
        if not {r["id"] for r in stage["replay"]} <= train:
            raise ValueError("PARITY_ACQUISITION_NOT_ACTUALLY_TAUGHT")


def validate_plan(plan: dict, legacy_root: Path) -> bool:
    """Strict source-and-oracle regeneration, not trust in a supplied digest."""
    _validate_structure(plan)
    if plan != _build(legacy_root):
        raise ValueError("PARITY_SOURCE_OR_ORACLE_CONTRACT_DRIFT")
    return True


def head_bindings(plan: dict) -> dict:
    return deepcopy(plan["heads"])


def predecessor_teaching_batch(legacy_root: Path, *, grade="B01",
                               seed=2001, method="standard") -> dict:
    """Execute the original School50 v10 batch compiler, without training.

    It already implemented instruction methods, exact acquisition replays,
    six direct-number answers, paired contrasts and historical rehearsal.
    Carry over its method semantics instead of writing a lookalike sampler.
    Old B codes remain provenance aliases, not admitted MLX grade names.
    """
    import random
    source, arithmetic, _, micro, graph, source_sha = _source_stack(legacy_root)
    library = importlib.import_module("bilqis_school.lessons")
    bridge = importlib.import_module("bilqis_school.spiral_semantic_bridge")
    for module, relative in ((library, "bilqis_school/lessons.py"),
                             (bridge, "bilqis_school/spiral_semantic_bridge.py")):
        if Path(module.__file__).resolve() != Path(legacy_root).resolve() / relative:
            raise ValueError("PARITY_TEACHER_SOURCE_ROOT_DRIFT")
    if grade not in source.GRADES:
        raise ValueError("PARITY_PREDECESSOR_GRADE_NOT_IN_SOURCE")
    rows, allocation = source.compile_batch(
        grade, library.TeacherLibrary(), graph, random.Random(seed), method=method)
    source.validate_rows(rows, graph, split="train", expected=48)
    mapping = {token: i for i, token in enumerate(graph["tokens"])}
    converted = []
    for row in rows:
        record = row["input"]
        if record.get("task") == arithmetic.VERSION:
            tokens = arithmetic.encode(record, mapping)
        elif record.get("task") == bridge.VERSION:
            tokens = bridge.encode(record, graph)
        else:
            tokens = library.encode(row, graph)
        kind = "numeric_0_3" if row["answer_kind"] == "numeric" else "evidence"
        gold = str(row["gold"]) if kind == "numeric_0_3" else row["gold"]
        if (kind == "numeric_0_3" and gold not in ("0", "1", "2", "3") or
                kind == "evidence" and gold not in micro.STATES or
                not tokens or len(tokens) > 96 or
                any(type(t) is not int or not 0 <= t < len(mapping) for t in tokens)):
            raise ValueError("PARITY_SOURCE_TEACHER_BATCH_CASTE_OR_CODEC_DRIFT")
        meta = row["course_meta"]
        native = _native_output(kind, gold, mapping)
        converted.append({"id": row["id"], "tokens": tokens,
                          "answer_kind": kind, "gold": gold,
                          **({"native_output": native} if native else {}),
                          "tranche": meta["tranche"],
                          "semantic_source_id": meta.get("semantic_source_id"),
                          "projection": meta.get("projection")})
    numeric_replay = [r["id"] for fold in ("primary", "confirm")
                      for r in source.numeric_panel(graph, fold=fold)]
    truth_replay = [r["id"] for fold in ("primary", "confirm")
                    for r in source.panel(grade, graph, fold=fold)]
    replay_ids = numeric_replay + truth_replay
    if (len(rows) != 48 or len(set(replay_ids)) != 16 or
            not set(replay_ids) <= {r["id"] for r in converted}):
        raise ValueError("PARITY_PREDECESSOR_REPLAY_NOT_TAUGHT")
    return {"source_sha256": source_sha, "method": method,
            "legacy_grade": grade, "rows": converted,
            "allocation": allocation, "replay_ids": replay_ids,
            "scope": "TEACHER_FIXTURE_REPLAY_NOT_NEW_GRADE_ADMISSION",
            "training_authorized": False}


def predecessor_instruction_choice(legacy_root: Path, teacher: dict, *,
                                   grade="B01", seed=9, used=()) -> str:
    """Reuse the original UCB lesson-method selection without teacher writes.

    Old B01 is an archived source label, never an admitted MLX grade.
    New methods and reward semantics require their own source-attested release.
    """
    import random
    source, _, _, _, _, _ = _source_stack(legacy_root)
    staged = importlib.import_module("bilqis_school.spiral_staged_runner")
    if Path(staged.__file__).resolve() != (Path(legacy_root).resolve() /
                                          "bilqis_school/spiral_staged_runner.py"):
        raise ValueError("PARITY_TEACHER_METHOD_SOURCE_ROOT_DRIFT")
    if grade not in source.GRADES:
        raise ValueError("PARITY_PREDECESSOR_GRADE_NOT_IN_SOURCE")
    chosen = staged._choose_instruction(
        deepcopy(teacher), grade, random.Random(seed), used=used)
    if chosen not in staged.INSTRUCTIONAL_METHODS:
        raise ValueError("PARITY_PREDECESSOR_METHOD_ABI_DRIFT")
    return chosen


def eligible_stage(plan: dict, stage: str, receipts: dict) -> bool:
    """Exposed acquisition gates never certify independent generalization."""
    if stage not in STAGE_ORDER:
        raise ValueError("PARITY_UNKNOWN_STAGE")
    for earlier in REQUIRES[stage]:
        evidence = receipts.get(earlier) or {}
        known = [r["id"] for r in plan["stages"][earlier]["replay"]]
        sha = evidence.get("student_sha256")
        if (evidence.get("status") != "ACQUIRED_ON_EXPOSED_REPLAY" or
                evidence.get("source_sha256") != plan["source_sha256"] or
                evidence.get("probe_ids") != known or
                evidence.get("total") != len(known) or
                evidence.get("correct") != len(known) or
                type(evidence.get("optimizer_step")) is not int or
                not isinstance(sha, str) or len(sha) != 64 or
                any(ch not in "0123456789abcdef" for ch in sha)):
            return False
    return True


def audit_summary(plan: dict) -> dict:
    """Safe operator-facing counts and teaching samples, no sealed answer leak."""
    sample = next(pair for pair in plan["pairs"]["train"]
                  if pair["source"] == ["ADD", 1, 2])
    return {
        "schema": plan["schema"],
        "source_sha256": plan["source_sha256"],
        "original_student_graph_sha256": plan["graph_sha256"],
        "source_partitions": {k: len(v) for k, v in plan["pairs"].items()},
        "stage_rows": {k: {name: len(value) for name, value in stage.items()
                           if name in ("train", "replay", "development", "sealed")}
                       for k, stage in plan["stages"].items()},
        "answer_classes": {k: len(h["values"]) for k, h in plan["heads"].items()},
        "example": {"source": "ADD(1,2)", "direct": sample["rows"][0]["gold"],
                    "native_output_identity": sample["rows"][0]["native_output"]["identity"],
                    "native_output_token_id": sample["rows"][0]["native_output"]["token_id"],
                    "correct_claim": sample["rows"][1]["gold"],
                    "incorrect_claim": sample["rows"][2]["gold"]},
        "first_training_gate": "NUMERAL_IDENTITY_EXPOSED_REPLAY_NOT_YET_MEASURED",
        "sealed_exam_policy": plan["sealed_exam_policy"],
        "training_authorized": plan["training_authorized"],
        "qualification_authorized": plan["qualification_authorized"],
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path,
                        default=Path(__file__).resolve().parents[2] / "bilqis-triplets-v16")
    args = parser.parse_args(argv)
    plan = build_plan(args.legacy_root)
    validate_plan(plan, args.legacy_root)
    print(json.dumps(audit_summary(plan), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
