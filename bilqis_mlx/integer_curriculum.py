"""Seeded, type-checked integer curriculum generated from the original oracle.

`BILQIS_INTEGER_MAX` bounds *exposed lessons and generated test operands*,
not the pretrained model vocabulary. This is an unadmitted teaching proposal;
it never writes an exam, updates the student, or changes the sealed Grade A.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import re

from .pedagogical_parity import _source_stack


ENV_INTEGER_MAX = "BILQIS_INTEGER_MAX"
DEFAULT_INTEGER_MAX = 3
SCHEMA = "bilqis.curriculum.typed-integer/v1"
LOCAL_ENV = Path(__file__).resolve().parents[1] / ".env"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                         separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class IntegerScope:
    maximum: int

    @classmethod
    def from_environment(cls, parity: dict, *, env_file: Path = LOCAL_ENV):
        """Exactly one numeric limit; process env overrides optional local .env."""
        raw = os.environ.get(ENV_INTEGER_MAX)
        if raw is None and env_file.exists():
            if env_file.is_symlink() or not env_file.is_file():
                raise ValueError("INTEGER_SCOPE_UNSAFE_ENV_FILE")
            matches = []
            for line in env_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or not stripped:
                    continue
                if ENV_INTEGER_MAX not in stripped:
                    continue
                match = re.fullmatch(
                    r"(?:export\s+)?BILQIS_INTEGER_MAX\s*=\s*(\S+)(?:\s+#.*)?",
                    stripped)
                if not match:
                    raise ValueError("INTEGER_SCOPE_MALFORMED_ENV_FILE_VALUE")
                matches.append(match.group(1))
            if len(matches) > 1:
                raise ValueError("INTEGER_SCOPE_DUPLICATED_ENV_FILE_VALUE")
            if matches:
                raw = matches[0]
        if raw is None:
            raw = str(DEFAULT_INTEGER_MAX)
        if not raw or not raw.isascii() or not raw.isdecimal():
            raise ValueError("INTEGER_SCOPE_INVALID_ENVIRONMENT_VALUE")
        return cls.checked(int(raw), parity)

    @classmethod
    def checked(cls, maximum: int, parity: dict):
        names = parity["heads"]["semantic_token"]["values"]
        approved = parity["heads"]["numeric_full_101"]["values"]
        if (type(maximum) is not int or maximum < 1 or maximum >= len(approved)
                or any("school.number." + str(i) not in names
                       for i in range(maximum + 1))):
            raise ValueError("INTEGER_SCOPE_OUTSIDE_PINNED_VOCABULARY")
        return cls(maximum)

    def head(self, parity: dict) -> dict:
        base = parity["heads"]["semantic_token"]["values"]
        return {"values": [str(i) for i in range(self.maximum + 1)],
                "token_ids": [base.index("school.number." + str(i))
                              for i in range(self.maximum + 1)]}


@dataclass(frozen=True)
class TypedOperation:
    name: str
    inputs: tuple[str, ...]
    output: str


def _operators(graph: dict) -> tuple[TypedOperation, ...]:
    """Derive arity, input types, and codomain from source graph signatures."""
    result = []
    for node in graph["nodes"]:
        if node["id"].startswith("school.op."):
            domain, codomain = node["signature"].split("->")
            inputs = tuple(domain.split("*"))
            if (len(inputs) != node["arity"] or
                    any(t not in ("Number", "Boolean") for t in (*inputs, codomain))):
                raise ValueError("INTEGER_SCOPE_SOURCE_TYPE_SIGNATURE_DRIFT")
            result.append(TypedOperation(node["subtype"], inputs, codomain))
    if (not any(x.name == "EQ" and x.inputs == ("Number", "Number")
                and x.output == "Boolean" for x in result) or
            not any(x.output == "Number" for x in result)):
        raise ValueError("INTEGER_SCOPE_SOURCE_OPERATORS_MISSING")
    return tuple(result)


def _partition(record_id: str) -> str:
    bucket = int(record_id[:12], 16) % 100
    return "train" if bucket < 70 else "development" if bucket < 85 else "sealed"


def _number_term(rng, arithmetic, operators, maximum):
    choices = [op.name for op in operators if op.inputs == ("Number", "Number")
               and op.output == "Number"]
    if not choices:
        raise ValueError("INTEGER_SCOPE_NUMBER_OPERATORS_MISSING")

    def operand(nested):
        leaf = arithmetic.atom(rng.randrange(maximum + 1))
        if not nested:
            return leaf
        op = rng.choice(choices)
        other = arithmetic.atom(rng.randrange(maximum + 1))
        if op == "MOD" and arithmetic.evaluate(other) == 0:
            return leaf
        possible = arithmetic.operation(op, leaf, other)
        result = arithmetic.evaluate(possible)
        return (possible if type(result) is int and 0 <= result <= maximum
                else leaf)

    name = rng.choice(choices)
    left = operand(rng.randrange(3) == 0)
    right = operand(rng.randrange(3) == 0)
    if name == "MOD" and arithmetic.evaluate(right) == 0:
        return None
    expression = arithmetic.operation(name, left, right)
    value = arithmetic.evaluate(expression)
    if type(value) is not int or not 0 <= value <= maximum:
        return None
    arithmetic.verify(expression)
    return expression, value


def _row(arithmetic, vocab, expression, *, source_id, partition, kind, gold,
         head, maximum):
    arithmetic.verify(expression)
    correct = arithmetic.evaluate(expression)
    observed = "TRUE" if correct is True else "FALSE" if correct is False else str(correct)
    if observed != gold:
        raise ValueError("INTEGER_SCOPE_SOURCE_ORACLE_GOLD_DRIFT")
    record = {"task": arithmetic.VERSION, "expression": expression}
    tokens = arithmetic.encode(record, vocab)
    binding = ({"identity": "school.number." + gold,
                "token_id": vocab["school.number." + gold]}
               if kind == head else None)
    if binding and int(gold) > maximum:
        raise ValueError("INTEGER_SCOPE_ANSWER_EXCEEDS_CAP")
    return {"id": _digest(record), "source_id": source_id,
            "partition": partition, "answer_kind": kind, "gold": gold,
            "record": record, "tokens": tokens,
            **({"native_output": binding} if binding else {}),
            "oracle": "bilqis_school.arithmetic.evaluate+independent_evaluate"}


def generate_integer_curriculum(parity: dict, legacy_root: Path, *, seed: int,
                                count: int, maximum: int | None = None) -> dict:
    """Generate fresh typed math/Boolean views with stable source partitions.

    A `seed` changes sampled expressions but never a source's partition.
    The passed maximum is for isolated tests; normal runs use the sole env var.
    """
    if type(seed) is not int or type(count) is not int or count < 1:
        raise ValueError("INTEGER_SCOPE_INVALID_GENERATOR_ARGUMENTS")
    scope = (IntegerScope.from_environment(parity) if maximum is None else
             IntegerScope.checked(maximum, parity))
    source, arithmetic, _, _, graph, original_sha = _source_stack(legacy_root)
    if parity["graph_sha256"] != _digest(graph):
        raise ValueError("INTEGER_SCOPE_UNEXPECTED_GRAPH_ABI")
    operations = _operators(graph)
    vocab = {name: idx for idx, name in enumerate(graph["tokens"])}
    heads = deepcopy(parity["heads"])
    heads["numeric_active"] = scope.head(parity)
    rng = random.Random(seed)
    results, seen = [], set()
    for _ in range(max(400, count * 80)):
        if len(results) >= count:
            break
        candidate = _number_term(rng, arithmetic, operations, scope.maximum)
        if candidate is None:
            continue
        expression, value = candidate
        record = {"task": arithmetic.VERSION, "expression": expression}
        source_id = _digest(record)
        if source_id in seen:
            continue
        seen.add(source_id)
        partition = _partition(source_id)
        incorrect = (value + 1) % (scope.maximum + 1)
        positive = arithmetic.operation("EQ", expression, arithmetic.atom(value))
        negative = arithmetic.operation("EQ", expression, arithmetic.atom(incorrect))
        views = [
            _row(arithmetic, vocab, expression, source_id=source_id,
                 partition=partition, kind="numeric_active", gold=str(value),
                 head="numeric_active", maximum=scope.maximum),
            _row(arithmetic, vocab, positive, source_id=source_id,
                 partition=partition, kind="evidence", gold="TRUE",
                 head="numeric_active", maximum=scope.maximum),
            _row(arithmetic, vocab, negative, source_id=source_id,
                 partition=partition, kind="evidence", gold="FALSE",
                 head="numeric_active", maximum=scope.maximum),
        ]
        if len({v["id"] for v in views}) != 3:
            raise ValueError("INTEGER_SCOPE_DUPLICATE_SEMANTIC_VIEW")
        results.append({"source_id": source_id, "partition": partition,
                        "source_type": "Number", "answer_type": "Number",
                        "value": value, "views": views})
    if len(results) != count:
        raise ValueError("INTEGER_SCOPE_DISTINCT_VARIATION_EXHAUSTED")
    return {"schema": SCHEMA, "integer_max": scope.maximum,
            "source_sha256": original_sha, "graph_sha256": parity["graph_sha256"],
            "seed": seed, "operators": [op.__dict__ for op in operations],
            "rows": results, "heads": heads, "training_authorized": False,
            "qualification_authorized": False,
            "scope": "TYPED_GENERATED_RESEARCH_PROPOSAL_NOT_FROZEN_EXAM"}
