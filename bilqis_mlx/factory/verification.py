"""Independent source/encoding agreement before generated rows reach the trainer."""
from __future__ import annotations

from ..verification.copular import VERSION as COPULAR_ORACLE


def check_copular(row, *, graph, **_):
    from ..source_adapters.copular import (
        decode, _record, _pattern, CAPABILITY, SYMBOL, GENERATOR, ORACLE, SENSE_ID,
    )
    from ..verification.copular import independent_answer
    from ..vocabulary_growth import digest
    try:
        record = row["record"]
        gold = independent_answer(record)
        tokens = row["tokens"]
        if (not isinstance(tokens, list) or
                any(type(index) is not int or not 0 <= index < len(graph["tokens"]) for index in tokens)):
            return False
        world, expression = decode([graph["tokens"][index] for index in tokens], graph)
        return (record == _record(world, expression) and
                row["gold"] == gold and row["id"] == row["source_id"] == digest(record) and
                row["capability"] == CAPABILITY and row["root"] == SYMBOL and
                row["generator"] == GENERATOR and row["oracle"] == ORACLE and
                row["answer_kind"] == "binary" and row["source_sense_id"] == SENSE_ID and
                row["universe_size"] == len(world.entities) and
                row["reference_pattern"] == _pattern(world, expression))
    except (KeyError, ValueError, TypeError, AttributeError):
        return False

from ..verification.event_frames import (
    VERSION as EVENT_FRAME_ORACLE, independent_answer as event_frame_answer,
)
