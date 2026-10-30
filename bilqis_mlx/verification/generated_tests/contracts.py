"""Generated-test family selection and immutable dependency identities."""
from __future__ import annotations
from bilqis_mlx.integer_curriculum import (IntegerScope, _partition,
                                 generate_integer_curriculum)
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
from bilqis_mlx.paths import REPO_ROOT


@dataclass(frozen=True)
class Family:
    name: str
    input_types: tuple[str, ...]
    output_type: str
    laws: tuple[str, ...] = ()

    @property
    def dependencies(self) -> tuple[str, ...]:
        types = set(self.input_types) | {self.output_type}
        return tuple(sorted({"type:integer" if kind == "Number" else
                             "type:boolean" for kind in types} |
                            {"law:" + law for law in self.laws}))


# These are generative *laws/types*, not enumerations of examples or golds.
# The source graph and two agreeing oracles determine every sampled answer.
FAMILIES = (
    Family("integer.direct", ("Number", "Number"), "Number"),
    Family("integer.truth", ("Number", "Number"), "Boolean"),
    Family("integer.equivalence", ("Number", "Number"), "Boolean",
           ("equivalence",)),
    Family("integer.inverse_negation", ("Number", "Number", "Boolean"),
           "Boolean", ("negation",)),
    Family("boolean.constants", ("Boolean",), "Boolean"),
)


SCHEMA = "bilqis.semantic.generated-tests/v1"


ROOT = REPO_ROOT / "artifacts" / "semantic-tests"


LEGACY = REPO_ROOT / "vendor" / "legacy-v16"


def _json(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object_hash(value) -> str:
    return _hash(_json(value))


def select_families(selector: str) -> tuple[str, ...]:
    if selector == "all":
        return tuple(f.name for f in FAMILIES)
    if selector.startswith("family:"):
        name = selector.removeprefix("family:")
        if name in {f.name for f in FAMILIES}:
            return (name,)
    if selector in {tag for f in FAMILIES for tag in f.dependencies}:
        return tuple(f.name for f in FAMILIES if selector in f.dependencies)
    raise ValueError("SEMANTIC_TEST_SELECTOR_UNSUPPORTED:" + selector)


def _dependency_state(family: Family, scope: IntegerScope, parity: dict) -> dict:
    result = {"source_sha256": parity["source_sha256"],
              "graph_sha256": parity["graph_sha256"]}
    if "type:integer" in family.dependencies:
        result["type:integer"] = scope.maximum
    return result
