"""Checks callbacks for the historical school source contract."""
from __future__ import annotations
from .shared import (inspect_boolean_identification, inspect_source_query,)


def check_predicate(row, *, source_root, **_):
    from ...grade_a_oracle import evaluate
    from ...grade_a_probe import read_sources
    micro, development, *_ = read_sources(source_root)
    library = micro if row["record"]["task"] == "micro" else development
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(library.encode(row["record"])) == row["tokens"])


def check_connective(row, *, source_root, graph, **_):
    from ...grade_b_oracle import evaluate
    if row["record"].get("task") == "evaluate":
        from ...live_grade_b import _encode_logic_record, _logic_source
        logic = _logic_source(source_root)
        return (evaluate(row["record"], row["capability"]) == row["gold"] and
                _encode_logic_record(logic, row["record"], graph) == row["tokens"])
    from ...grade_a_probe import read_sources
    micro, *_ = read_sources(source_root)
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(micro.encode(row["record"])) == row["tokens"])


def check_boolean_composite(row, *, source_root, graph, **_):
    from ...boolean_composite_oracle import evaluate
    if row["record"].get("task") == "evaluate":
        from ...live_grade_b import _encode_logic_record, _logic_source
        logic = _logic_source(source_root)
        return (evaluate(row["record"], row["capability"]) == row["gold"] and
                _encode_logic_record(logic, row["record"], graph) == row["tokens"])
    from ...grade_a_probe import read_sources
    micro, *_ = read_sources(source_root)
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(micro.encode(row["record"])) == row["tokens"])


def semantic_footprint(row: dict) -> tuple[str, ...]:
    """Inspect source operations and omit literal/entity/codec representation."""
    record = row["record"]
    if record.get("task") == "identify_boolean_operator":
        from ...boolean_identification_oracle import evaluate
        root = "cogal.operator." + evaluate(record, row["capability"])
        shape = inspect_boolean_identification(record, root)
    else:
        shape = inspect_source_query(record["query"])
    return tuple(dict.fromkeys(shape.rooted_operators))

for _callback in (check_predicate, check_connective, check_boolean_composite, semantic_footprint,):
    _callback.__module__ = "bilqis_mlx.source_adapters.school"
