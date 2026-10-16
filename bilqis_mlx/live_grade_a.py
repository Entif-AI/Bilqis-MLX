"""Human-operated Grade A construction from pinned typed source predicates.

Seeds select new semantic instances. The rubric identifies the stable *rules*,
whereas every scored cohort carries its own distinct content digest. The
historical 144/72 manifest remains an immutable legacy evidence artifact.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from .grade_a_oracle import evaluate as independent_oracle
from .grade_a_probe import FAMILIES, make_record, read_sources


GENERATOR = "bilqis.mlx.grade-a-live-constructor/v1"
RELEASE = "bilqis.mlx.grade-a-live/20261015"
ASSESSMENT_ITEMS_PER_CAPABILITY = 12


def generator_source_digest():
    """Bind admitted sampling semantics to executable source bytes."""
    folder = Path(__file__).resolve().parent
    return _sha({name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                 for name in ("live_grade_a.py", "grade_a_probe.py",
                              "grade_a_oracle.py")})


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def live_course(accepted):
    """Version the source-defined rubric independently of sampled identities."""
    grade = accepted.grades[0]
    if set(c.id for c in grade.capabilities) != {c[0] for c in FAMILIES}:
        raise ValueError("LIVE_GRADE_A_UNEXPECTED_PREDICATE_SCOPE")
    rubric = _sha({"generator": GENERATOR, "generator_code_sha256": generator_source_digest(),
                   "source": accepted.source_attestation_sha256,
                   "families": [c.id for c in grade.capabilities],
                   "assessments_per_capability": ASSESSMENT_ITEMS_PER_CAPABILITY})
    current = replace(grade, assessment_sha256=rubric,
                      exam_item_counts=tuple((c.id, ASSESSMENT_ITEMS_PER_CAPABILITY)
                                             for c in grade.capabilities))
    course = replace(accepted, grades=(current,), version=RELEASE,
                     assessment_manifest_sha256=rubric)
    if not course.executable:
        raise ValueError("LIVE_GRADE_A_NOT_EXECUTABLE")
    return course


def draw_predicates(legacy_root: Path, graph: dict, *, seed: int,
                    each: int = ASSESSMENT_ITEMS_PER_CAPABILITY,
                    capability: str | None = None) -> tuple[dict, ...]:
    """Draw balanced, independently oracle-checked rows on every invocation."""
    if type(seed) is not int or type(each) is not int or each < 2 or each % 2:
        raise ValueError("LIVE_GRADE_A_INVALID_DRAW")
    micro, development, source_graph, _, _ = read_sources(legacy_root)
    if graph["tokens"][:len(source_graph["tokens"])] != source_graph["tokens"]:
        raise ValueError("LIVE_GRADE_A_STUDENT_SOURCE_VOCABULARY_DRIFT")
    capabilities = [f[0] for f in FAMILIES]
    if capability is not None:
        if capability not in capabilities:
            raise ValueError("LIVE_GRADE_A_UNKNOWN_CAPABILITY")
        capabilities = [capability]
    results = []
    seen = set()
    for cap in capabilities:
        rng = random.Random(_sha([GENERATOR, seed, cap]))
        # No sealed/train ownership: all draws are publicly reusable lessons.
        for index in range(each):
            truth = index % 2 == 0
            size = 3 if (index // 2) % 2 == 0 else 4
            for _ in range(3000):
                record, library = make_record(cap, rng, truth, split="train",
                    micro=micro, development=development, universe_size=size)
                gold = library.evaluate(record)
                if (gold != library.independent_evaluate(record) or
                        gold != independent_oracle(record, cap) or
                        gold != ("TRUE" if truth else "FALSE")):
                    raise ValueError("LIVE_GRADE_A_SOURCE_ORACLES_DISAGREE:" + cap)
                token_ids = list(library.encode(record))
                if (not 1 <= len(token_ids) <= 96 or min(token_ids) < 0 or
                        max(token_ids) >= len(graph["tokens"])):
                    raise ValueError("LIVE_GRADE_A_UNATTESTED_TOKENS_OR_CONTEXT")
                identity = _sha(record)
                if identity not in seen:
                    break
            else:
                raise ValueError("LIVE_GRADE_A_SEMANTIC_VARIANTS_EXHAUSTED:" + cap)
            seen.add(identity)
            results.append({"id": identity, "source_id": identity,
                "capability": cap, "answer_kind": "binary", "gold": gold,
                "tokens": token_ids, "record": record, "universe_size": size,
                "oracle": "original+independent+grade_a_oracle",
                "generator": GENERATOR})
    return tuple(results)
