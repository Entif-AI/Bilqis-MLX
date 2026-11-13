"""Immutable observation-only evidence for the read-only BAMF cockpit."""
from collections.abc import Mapping
from dataclasses import dataclass, fields
import json

from bilqis_mlx.errors import ErrorBus, SCHOOL


def _require(condition, reason):
    if not condition:
        ErrorBus.Raise(SCHOOL.BAMF_OPERATOR.INVALID, reason=reason)


def _count(value):
    return type(value) is int and value >= 0


def _digest(value):
    return (type(value) is str and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


def _label(value):
    return (type(value) is str and 1 <= len(value) <= 96
            and bool(value.strip()) and value.isprintable())


@dataclass(frozen=True)
class MeasuredScore:
    correct: int
    total: int
    source_sha256: str
    rubric_sha256: str


@dataclass(frozen=True)
class OperatorEvidence:
    candidate_sha256: str | None = None
    parent_sha256: str | None = None
    delivered_work_sha256: str | None = None
    delivered_rows: int | None = None
    grade_debt: tuple[tuple[str, int], ...] | None = None
    capability_debt: tuple[tuple[str, int], ...] | None = None
    promotion_attempts: int | None = None
    whole_school_fresh_retention: MeasuredScore | None = None
    learned_transfer: MeasuredScore | None = None
    historical_policies: tuple[str, ...] = ()


def _score(value):
    if value is None:
        return None
    _require(isinstance(value, Mapping) and set(value) == {
        'correct', 'total', 'source_sha256', 'rubric_sha256'}, 'evidence score fields')
    _require(_count(value['correct']) and _count(value['total'])
             and value['correct'] <= value['total']
             and _digest(value['source_sha256']) and _digest(value['rubric_sha256']),
             'evidence score values')
    return MeasuredScore(**value)


def _debt(value):
    if value is None:
        return None
    _require(isinstance(value, Mapping) and all(
        _label(k) and _count(v) for k, v in value.items()), 'evidence debt values')
    return tuple(sorted(value.items()))


def parse_evidence(value):
    """Copy optional receipt fields; structural validity is not producer authority."""
    if value is None:
        return OperatorEvidence()
    _require(isinstance(value, Mapping) and not set(value) - {
        f.name for f in fields(OperatorEvidence)}, 'evidence fields')
    result = {}
    for key in ('candidate_sha256', 'parent_sha256', 'delivered_work_sha256'):
        item = value.get(key)
        _require(item is None or _digest(item), 'evidence ' + key)
        result[key] = item
    for key in ('delivered_rows', 'promotion_attempts'):
        item = value.get(key)
        _require(item is None or _count(item), 'evidence ' + key)
        result[key] = item
    for key in ('grade_debt', 'capability_debt'):
        result[key] = _debt(value.get(key))
    for key in ('whole_school_fresh_retention', 'learned_transfer'):
        result[key] = _score(value.get(key))
    policies = value.get('historical_policies', [])
    _require(type(policies) is list and all(_label(p) for p in policies),
             'evidence historical policy labels')
    _require(len(set(policies)) == len(policies), 'evidence duplicate historical policies')
    return OperatorEvidence(**result, historical_policies=tuple(policies))


def compact_debt(evidence):
    if evidence.grade_debt is None and evidence.capability_debt is None:
        return 'debt NOT MEASURED'
    return ' | '.join(name + (' NOT MEASURED' if value is None else ' measured (details)')
                      for name, value in (('grade debt', evidence.grade_debt),
                                          ('capability debt', evidence.capability_debt)))


def render_evidence(evidence):
    """Render supplied observations separately; never infer learning or eligibility."""
    lines = []
    for label, value in (
        ('candidate', evidence.candidate_sha256), ('parent', evidence.parent_sha256),
        ('delivered work', evidence.delivered_work_sha256),
        ('delivered rows', evidence.delivered_rows),
    ):
        lines.append(f'{label} {value if value is not None else "NOT MEASURED"}')
    for label, debt in (('grade debt', evidence.grade_debt),
                        ('capability debt', evidence.capability_debt)):
        if debt is None:
            lines.append(label + ' NOT MEASURED')
        elif not debt:
            lines.append(label + ' none')
        else:
            lines.extend(f'{label} {name}={count}' for name, count in debt)
    count = evidence.promotion_attempts
    lines.append(f'promotion attempts {count if count is not None else "NOT MEASURED"}')
    for label, short, score in (
        ('whole-school fresh retention', 'retention', evidence.whole_school_fresh_retention),
        ('learned transfer', 'transfer', evidence.learned_transfer),
    ):
        observed = f'{score.correct}/{score.total}' if score is not None and score.total else 'NOT MEASURED'
        lines.append(label + ' ' + observed)
        lines.append(short + ' source ' + (score.source_sha256 if score else 'NOT MEASURED'))
        lines.append(short + ' rubric ' + (score.rubric_sha256 if score else 'NOT MEASURED'))
    lines.extend('historical policy (lineage only) ' + policy
                 for policy in evidence.historical_policies or ('NOT MEASURED',))
    # The terminal renderer is ASCII-only; escapes preserve distinct Unicode labels.
    return tuple('ATLAS EVIDENCE | ' + json.dumps(line, ensure_ascii=True)[1:-1]
                 for line in lines)
