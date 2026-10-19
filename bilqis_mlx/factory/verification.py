"""Independent source/encoding agreement before generated rows reach the trainer."""
from __future__ import annotations

def check_predicate(row, *, source_root, **_):
    from ..grade_a_oracle import evaluate
    from ..grade_a_probe import read_sources
    micro, development, *_ = read_sources(source_root)
    library = micro if row["record"]["task"] == "micro" else development
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(library.encode(row["record"])) == row["tokens"])


def check_connective(row, *, source_root, **_):
    from ..grade_b_oracle import evaluate
    from ..grade_a_probe import read_sources
    micro, *_ = read_sources(source_root)
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(micro.encode(row["record"])) == row["tokens"])


def check_numeric(row, *, graph, **_):
    from ..source_adapters.numeric import decode
    from ..verification.numeric import independent_value
    value = independent_value(decode(row["record"]["symbols"]))
    gold = ("TRUE" if value else "FALSE") if type(value) is bool else str(value)
    return (gold == row["gold"] and
            [graph["tokens"][index] for index in row["tokens"]] ==
            row["record"]["symbols"])


