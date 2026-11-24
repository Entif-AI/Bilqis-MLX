"""Complete construction geometry of repository-owned source adapters."""

from dataclasses import dataclass
from enum import Enum
from bilqis_mlx.learning.native_lesson_selection import LessonGroup


NUMERIC_LESSON_GROUP_WIDTH = 3
PAIRED_LESSON_GROUP_WIDTH = 2


class LessonGeometryError(str, Enum):
    NUMERIC_CONSTRUCTION = "invalid numeric lesson construction"
    PAIRED_GOLD = "invalid paired lesson gold"
    COPULAR_PAIR = "invalid copular lesson pair"
    EVENT_PAIR = "invalid event lesson pair"


@dataclass(frozen=True)
class LessonGeometry:
    layout: str
    maximum: int | None = None
    provider: str = ""

    def expanded_count(self, requested):
        count = min(2 * requested, self.maximum or 128, 128)
        return count - count % NUMERIC_LESSON_GROUP_WIDTH if self.layout == "numeric" else count


def geometry_for_adapter(adapter):
    """Recognize actual source constructors, never a capability-name prefix."""
    from .grade_a_presentation import draw_a
    from ._school.boolean import draw_b, draw_b_composite_release, draw_b_idboolops_release
    from ._school.numeric import draw_c
    from .copular import draw as copular
    from .event_frames import draw as frames
    from .event_intro import draw as intro
    from .event_pairs import draw as pairs
    from .c13_episode import MAX_DRAW_EACH, draw_episode
    draw = adapter.draw
    if draw is draw_c:
        return LessonGeometry("numeric")
    if draw is copular:
        return LessonGeometry("copular", 10000)
    if draw is pairs:
        return LessonGeometry("event-pair", provider="event")
    if draw is draw_episode:
        return LessonGeometry("episode", MAX_DRAW_EACH)
    if draw is draw_a:
        return LessonGeometry("singleton", provider="predicate")
    if any(draw is item for item in (draw_b, draw_b_composite_release, draw_b_idboolops_release)):
        return LessonGeometry("singleton", provider="boolean")
    if draw is frames or draw is intro:
        return LessonGeometry("singleton", provider="event")
    return None


def _validate_numeric(group):
    if (len({row["source_id"] for row in group}) != 1
            or group[0].get("answer_kind") != "numeric_active"
            or [(row.get("answer_kind", "binary"), row["gold"])
                for row in group[1:]] != [("binary", "TRUE"), ("binary", "FALSE")]):
        raise ValueError(LessonGeometryError.NUMERIC_CONSTRUCTION.value)


def _validate_pair(group, layout):
    first, second = group
    a, b = first["record"], second["record"]
    if {first["gold"], second["gold"]} != {"TRUE", "FALSE"}:
        raise ValueError(LessonGeometryError.PAIRED_GOLD.value)
    if layout == "copular":
        if (a["query"] != b["query"] or a["entities"] != b["entities"]
                or len(a["denotations"]) != len(b["denotations"])
                or sum(x != y for x, y in zip(a["denotations"], b["denotations"])) != 1):
            raise ValueError(LessonGeometryError.COPULAR_PAIR.value)
    elif a["events"] != b["events"] or a["query"] == b["query"]:
        raise ValueError(LessonGeometryError.EVENT_PAIR.value)


def _event_pattern(row):
    record = row["record"]
    event = next(event for event in record["events"] if event[0] == record["query"])
    return tuple(event[1:])


def _stratum(rows, geometry):
    layout = geometry.layout
    return tuple((
        row["capability"], row.get("answer_kind", "binary"),
        row["gold"] if row.get("answer_kind", "binary") in ("binary", "boolean_operator") else None,
        tuple(row.get("operand_truths", ())), tuple(row.get("operators", ())),
        tuple(row.get("operator_roots", ())), row.get("composition_width"),
        row.get("composition_pass"), row.get("reference_pattern"),
        row["record"]["depth"] if layout == "episode" else None,
        row["record"]["query"] if layout == "episode" else None,
        _event_pattern(row) if geometry.provider == "event" else None,
    ) for row in rows)


def complete_groups(rows, geometry):
    """Partition by the source constructor's declared occurrence layout."""
    layout = geometry.layout
    groups = []
    offset = 0
    while offset < len(rows):
        if layout == "numeric":
            width = NUMERIC_LESSON_GROUP_WIDTH
        elif layout == "copular":
            width = (2, 2, 2, 2, 1, 1, 1, 1)[len(groups) % 8]
        elif layout == "event-pair" and offset == 0 and len(rows) >= PAIRED_LESSON_GROUP_WIDTH:
            width = PAIRED_LESSON_GROUP_WIDTH
        else:
            width = 1
        group = tuple(rows[offset:offset + width])
        if len(group) != width:
            break
        if layout == "numeric":
            _validate_numeric(group)
        elif width == PAIRED_LESSON_GROUP_WIDTH:
            _validate_pair(group, layout)
        groups.append(LessonGroup(group, _stratum(group, geometry)))
        offset += width
    return tuple(groups)


def distinct_groups(groups):
    """Drop whole colliding constructions, never an individual view."""
    ids, tokens, retained = set(), set(), []
    for group in groups:
        group_ids = {row["id"] for row in group.rows}
        group_tokens = {tuple(row["tokens"]) for row in group.rows}
        if (len(group_ids) != len(group.rows) or len(group_tokens) != len(group.rows)
                or ids & group_ids or tokens & group_tokens):
            continue
        ids.update(group_ids)
        tokens.update(group_tokens)
        retained.append(group)
    return tuple(retained)
