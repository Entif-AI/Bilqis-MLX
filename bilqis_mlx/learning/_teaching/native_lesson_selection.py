"""Select interchangeable, complete source groups without changing custody."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from random import Random
from typing import Hashable


class LessonCapacityError(ValueError):
    """The supplied pool cannot fill the baseline strata."""


@dataclass(frozen=True)
class LessonGroup:
    """Source-owner supplied rows and mandatory coverage stratum."""

    rows: tuple[dict, ...]
    stratum: Hashable


@dataclass(frozen=True)
class LessonSelection:
    groups: tuple[LessonGroup, ...]
    depth_control: str | None
    contrast_control: str | None
    token_count: int
    signature_count: int

    @property
    def rows(self):
        return tuple(row for group in self.groups for row in group.rows)


def _validate_groups(groups):
    if not groups:
        raise ValueError("empty lesson groups")
    ids, tokens = set(), set()
    for group in groups:
        if not isinstance(group, LessonGroup) or not group.rows:
            raise ValueError("empty or invalid lesson group")
        hash(group.stratum)
        for row in group.rows:
            if not isinstance(row, dict):
                raise ValueError("invalid lesson row")
            identity, sequence = row.get("id"), row.get("tokens")
            if (not isinstance(identity, str) or not identity
                    or not isinstance(sequence, (list, tuple)) or not sequence
                    or any(type(token) is not int for token in sequence)
                    or not isinstance(row.get("answer_kind", "binary"), str)
                    or not isinstance(row.get("gold"), str)):
                raise ValueError("invalid lesson row")
            sequence = tuple(sequence)
            if identity in ids or sequence in tokens:
                raise ValueError("duplicate lesson row identity or token tuple")
            ids.add(identity)
            tokens.add(sequence)


def _key(group):
    return len(group.rows), group.stratum


def _signature(group):
    return tuple(sorted({(row.get("answer_kind", "binary"), row["gold"])
                         for row in group.rows}))


def _depth(group):
    return sum(len(row["tokens"]) for row in group.rows)


@dataclass(frozen=True)
class _Option:
    group: LessonGroup
    index: int
    depth: int
    signature: tuple[tuple[str, str], ...]

    def rank(self, deep, contrast, counts):
        return (-self.depth if deep else 0,
                counts[self.signature] if contrast else 0, self.index)


@dataclass(frozen=True)
class _Variant:
    groups: tuple[LessonGroup, ...]
    token_count: int
    signature_count: int


def _options(pool, seed):
    shuffled = list(pool)
    Random(seed).shuffle(shuffled)
    strata = defaultdict(list)
    for index, group in enumerate(shuffled):
        strata[_key(group)].append(
            _Option(group, index, _depth(group), _signature(group)))
    return strata


def _variant(slots, strata, *, deep, contrast):
    remaining = {key: list(options) for key, options in strata.items()}
    counts = Counter()
    selected = []
    tokens = 0
    for slot in slots:
        options = remaining[slot]
        choice = min(options, key=lambda item: item.rank(deep, contrast, counts))
        options.remove(choice)
        counts[choice.signature] += 1
        selected.append(choice.group)
        tokens += choice.depth
    return _Variant(tuple(selected), tokens, len(counts))


def select_group_lesson(baseline, pool, *, seed, deep, contrast):
    """Fill exact baseline slots; credit only paired, realized policy effects.

    Completeness, coverage semantics and source authority belong to the caller.
    The selector retains original row references and never mints source grants.
    """
    _validate_groups(baseline)
    _validate_groups(pool)
    slots = tuple(map(_key, baseline))
    strata = _options(pool, seed)
    if any(len(strata.get(key, ())) < count
           for key, count in Counter(slots).items()):
        raise LessonCapacityError("insufficient complete-group stratum capacity")
    a = _variant(slots, strata, deep=False, contrast=False)
    b = _variant(slots, strata, deep=True, contrast=False)
    c = _variant(slots, strata, deep=False, contrast=True)
    d = _variant(slots, strata, deep=True, contrast=True)
    if c.signature_count <= a.signature_count:
        c = a
    if b.token_count <= a.token_count:
        b = a
    candidates = (b, c, d) if c.token_count == b.token_count else (b, d)
    d = max(candidates, key=lambda variant: variant.signature_count)
    chosen = (d if contrast else b) if deep else (c if contrast else a)
    low, high = (c, d) if contrast else (a, b)
    depth_effect = high.token_count > low.token_count
    low, high = (b, d) if deep else (a, c)
    contrast_effect = high.signature_count > low.signature_count
    depth_control = ("SOURCE_TOKEN_LENGTH_PROXY" if deep
                     else "UNBIASED_SOURCE_GROUPS") if depth_effect else None
    contrast_control = ("SOURCE_GROUP_DIVERSITY" if contrast
                        else "SOURCE_GROUP_RANDOM") if contrast_effect else None
    return LessonSelection(chosen.groups, depth_control, contrast_control,
                           chosen.token_count, chosen.signature_count)
