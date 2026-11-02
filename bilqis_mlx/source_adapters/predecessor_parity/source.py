"""Exact historical source and original checkpoint custody."""
import hashlib
import importlib
from pathlib import Path
from ...backup import digest_file
from ...grade_a_probe import PINNED_FULL_STUDENT_GRAPH_SHA256, read_sources
from ...source import AUDITED_PARENT
from ...semantics.abi import HISTORICAL_PREFIX_SIZE
from .contracts import PREDECESSOR, _digest

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
