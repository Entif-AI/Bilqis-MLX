"""School50 checkpoint-compatible arithmetic answer-target A/B contract.

The *same* original School50 Boolean equality question is presented to both
learners, with the *same* tokens and mathematical expression. The experiment
changes only the answer target and its tied-embedding readout:

  evidence control: TRUE/FALSE from the model's original 5-state readout;
  numeric treatment: integer value of equality's LEFT arithmetic expression,
      predicted against the original 101 school.number.0..100 embedding rows.

No new vocabulary, model parameters, tokenizer, geometry, optimizer schema,
teacher mutation, or v2/v3 curriculum is introduced. Both outcomes are
independently computed from School50's original arithmetic oracle.
"""
from __future__ import annotations

from collections import Counter
import random

import torch
from torch.nn import functional as F

from bilqis_logic.kernel import digest
from bilqis_micro.graph import STATES
from bilqis_ref.model import batch
from . import arithmetic, lessons

VERSION = "bilqis.school50.numeric-answer-isolation/v2"
ARMS = ("binary", "numeric")
GRADES = (20, 22)
SPLIT_BUCKETS = {"train": frozenset((0, 1, 2, 3, 4, 5)),
                 "development": frozenset((6, 7)),
                 "sealed": frozenset((8, 9))}
NUMBER_TOKENS = tuple("school.number." + str(n) for n in range(101))


def numeric_token_ids(graph):
    mapping = {token: index for index, token in enumerate(graph["tokens"])}
    if len(mapping) != len(graph["tokens"]) or any(token not in mapping for token in NUMBER_TOKENS):
        raise ValueError("NUMERIC_ABI_MISSING_NUMBER_TOKENS")
    result = tuple(mapping[t] for t in NUMBER_TOKENS)
    if len(set(result)) != 101:
        raise ValueError("NUMERIC_ABI_COLLIDING_CLASSES")
    return result


def readout(model, ids, lengths, *, answer_kind, number_ids):
    """Identical hidden state and tied readout mechanism for both arms.

    This duplicates MicroStudent.forward's forward-path computation without
    modifying the original class or pretrained state. `evidence` must agree
    numerically with the original model.forward for every input.
    """
    if answer_kind not in ("evidence", "numeric"):
        raise ValueError("NUMERIC_UNSUPPORTED_ANSWER_KIND")
    if (ids.ndim != 2 or lengths.shape != (ids.shape[0],) or
            ids.shape[1] > model.config.context or
            bool((lengths < 1).any()) or bool((lengths > ids.shape[1]).any())):
        raise ValueError("NUMERIC_INPUT_SHAPE_OR_CONTEXT")
    positions = torch.arange(ids.shape[1], device=ids.device)
    x = model.embedding(ids) + model.position(positions)[None]
    for block in model.blocks:
        x = block(x)
    hidden = model.norm(x)[torch.arange(ids.shape[0], device=ids.device), lengths - 1]
    answer_ids = (model.answer_ids if answer_kind == "evidence" else
                  torch.tensor(number_ids, dtype=torch.long, device=ids.device))
    return F.linear(hidden, model.embedding(answer_ids))


def answer_gold(question):
    """Reject ambiguous/forged labels with the legacy independent interpreter."""
    if question.get("family") not in ("math:G20", "math:G22"):
        raise ValueError("NUMERIC_QUESTION_NOT_A_TARGET_GRADE")
    expression = question["input"]["expression"]
    if (question["input"]["task"] != arithmetic.VERSION or
            expression["kind"] != "op" or expression["name"] != "EQ" or
            expression["args"][0]["kind"] != "op" or
            expression["args"][1]["kind"] != "number"):
        raise ValueError("NUMERIC_QUESTION_NOT_A_SCHOOL50_EQUALITY")
    arithmetic.verify(expression)
    value = arithmetic.evaluate(expression["args"][0])
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError("NUMERIC_TARGET_OUTSIDE_EXISTING_ABI")
    gold = "TRUE" if arithmetic.evaluate(expression) else "FALSE"
    if gold != question["gold"]:
        raise ValueError("NUMERIC_BINARY_GOLD_DRIFT")
    return value


def _expression_pair(grade, rng):
    """One original math expression, plus true and off-by-one equality views."""
    if grade not in GRADES:
        raise ValueError("NUMERIC_UNSUPPORTED_EXPRESSION_GRADE")
    for _ in range(2000):
        term = arithmetic._term(rng, grade)
        result = arithmetic.evaluate(term)
        if type(result) is not int or not 0 <= result <= 100:
            continue
        arithmetic.verify(term)
        altered = result + 1 if result < 100 else result - 1
        positive = arithmetic.row(arithmetic.operation("EQ", term, arithmetic.atom(result)), grade)
        negative = arithmetic.row(arithmetic.operation("EQ", term, arithmetic.atom(altered)), grade)
        if answer_gold(positive) != result or answer_gold(negative) != result:
            raise ValueError("NUMERIC_SHARED_SEMANTICS_MISMATCH")
        if positive["gold"] != "TRUE" or negative["gold"] != "FALSE":
            raise ValueError("NUMERIC_BOOL_CONTRAST_UNSOUND")
        identity = digest(term)
        return {"grade": grade, "expression_id": identity, "numeric_gold": result,
                "true": positive, "false": negative}
    raise ValueError("NUMERIC_CANNOT_CREATE_ORACLE_VERIFIED_PAIR")


def split_of(expression_id):
    if len(expression_id) != 64:
        raise ValueError("NUMERIC_EXPRESSION_ID_MALFORMED")
    bucket = int(expression_id[:12], 16) % 10
    return next(name for name, buckets in SPLIT_BUCKETS.items() if bucket in buckets)


def panel(split, *, expressions_per_grade, seed, exclude_expression_ids=()):
    if split not in SPLIT_BUCKETS or not 1 <= expressions_per_grade <= 256:
        raise ValueError("NUMERIC_PANEL_BAD_PROFILE")
    excluded = set(exclude_expression_ids)
    pairs = []
    accepted = set()
    for grade in GRADES:
        rng = random.Random(seed + grade * 1009)
        attempts = 0
        grade_pairs = []
        while len(grade_pairs) < expressions_per_grade:
            attempts += 1
            if attempts > expressions_per_grade * 8000:
                raise ValueError("NUMERIC_PANEL_NOT_ENOUGH_DISJOINT_EXPRESSIONS")
            pair = _expression_pair(grade, rng)
            identity = pair["expression_id"]
            if (split_of(identity) != split or identity in excluded or
                    identity in accepted):
                continue
            grade_pairs.append(pair)
            accepted.add(identity)
        pairs.extend(grade_pairs)
    rng = random.Random(seed ^ 0x4AC231)
    rng.shuffle(pairs)
    return pairs


def flatten(pairs):
    """Binary labels are balanced; numerical answers do not depend on RHS."""
    result = []
    for index, pair in enumerate(pairs):
        rows = (pair["true"], pair["false"]) if index % 2 else (pair["false"], pair["true"])
        result.extend(rows)
    if len(result) != 2 * len(pairs):
        raise ValueError("NUMERIC_PAIR_TRUNCATED")
    if Counter(row["gold"] for row in result) != {"TRUE": len(pairs), "FALSE": len(pairs)}:
        raise ValueError("NUMERIC_BINARY_CLASS_IMBALANCE")
    return result


def encode_questions(rows, graph, device):
    lessons.valid_rows(rows, graph)
    return batch([lessons.encode(row, graph) for row in rows], device=device)


def rehearsal(library, graph, *, step, seed, count=16):
    """Original School50 lesson creators; exactly the same rows in both arms."""
    if count != 16:
        raise ValueError("NUMERIC_REHEARSAL_CONTRACT_CHANGED")
    rng = random.Random(seed + step * 104729 + 17)
    rows = []
    for index in range(count):
        grade = 1 + (step * 7 + index) % 18
        original_depth = (1, 2, 3)[(step + index) % 3]
        original_composition = index % 2 == 0
        # A particular G16 deep world at step 679 exceeded the source model's
        # 96-token context and aborted an otherwise durable paired training
        # run. Resample *only* that known generator limitation; preserve grade,
        # gold authority and deterministic RNG state. Never truncate the AST
        # or silently relabel an oversized question.
        for attempt in range(64):
            relaxed = attempt >= 32
            depth = 1 if relaxed else original_depth
            composition = False if relaxed else original_composition
            try:
                packet = library.one(grade, rng, depth=depth,
                                     prefer_composition=composition)
                candidate = packet[index % len(packet)] if isinstance(packet, list) else packet
                lessons.valid_rows([candidate], graph)
            except ValueError as exc:
                if str(exc) == "world exceeds preserved context":
                    continue
                raise
            row = dict(candidate)
            row["course_meta"] = {"tranche": "rehearsal", "origin_grade": grade,
                                  "resampling_attempts": attempt,
                                  "difficulty_fallback": relaxed,
                                  "difficulty_certification": "legacy_unverified"}
            rows.append(row)
            break
        else:
            raise RuntimeError("NUMERIC_REHEARSAL_CONTEXT_RESAMPLING_EXHAUSTED")
    lessons.valid_rows(rows, graph)
    return rows
