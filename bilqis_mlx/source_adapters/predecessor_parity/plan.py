"""Immutable-source construction and strict regeneration of parity plans."""
from copy import deepcopy
from pathlib import Path
from .contracts import SCHEMA, PREDECESSOR, REQUIRES, _digest
from .source import _source_stack, _answer_heads
from .lessons import _pair, _row
from .validation import _validate_structure

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


def validate_plan(plan: dict, legacy_root: Path) -> bool:
    """Strict source-and-oracle regeneration, not trust in a supplied digest."""
    _validate_structure(plan)
    if plan != _build(legacy_root):
        raise ValueError("PARITY_SOURCE_OR_ORACLE_CONTRACT_DRIFT")
    return True
