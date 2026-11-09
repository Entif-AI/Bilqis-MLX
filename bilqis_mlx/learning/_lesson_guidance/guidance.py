"""Read-only frozen-mentor row selection and gradient guidance."""
from __future__ import annotations

import bilqis_mlx.learning.champion_confidence as _learning_champion_confidence
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.mlx_parity as _runtime_mlx_parity

def _mentor_vote_specs(mentor, row_capabilities, *, lesson_grade,
                       direct_capabilities):
    """Return per-role row masks; same-grade soup fills uncovered capability rows."""
    import numpy as np
    capabilities = tuple(mentor.get("capabilities", ()))
    if capabilities:
        return tuple(
            (1, np.asarray(
                [row_capability == capability
                 for row_capability in row_capabilities],
                dtype=bool))
            for capability in capabilities
        )
    breadth = mentor.get("breadth")
    if mentor.get("soup_grade") == lesson_grade and direct_capabilities:
        mask = np.asarray(
            [capability not in direct_capabilities
             for capability in row_capabilities],
            dtype=bool)
    else:
        mask = np.ones(len(row_capabilities), dtype=bool)
    return ((breadth, mask),)


def _champion_directed_rows(mx, mentors, student_weights, rows, config,
                            answer_ids):
    """Source-gated rows where an owning champion is right and student is wrong."""
    if not mentors or not rows:
        return ()
    student_predictions = _learning_student_ops._predictions(
        mx, student_weights, rows, config, answer_ids)
    directed = set()
    for mentor in mentors:
        capabilities = set(mentor.get("capabilities", ()))
        graph = mentor.get("graph")
        if not capabilities or not isinstance(graph, dict):
            continue
        vocabulary = len(graph.get("tokens", ()))
        eligible = [
            row for row in rows
            if row.get("capability") in capabilities and
            row.get("tokens") and max(row["tokens"]) < vocabulary
        ]
        if not eligible:
            continue
        mentor_config = _learning_student_ops._compatible_answer_config(
            config, graph)
        predictions = _learning_student_ops._predictions(
            mx, mentor["weights"], eligible, mentor_config, answer_ids)
        for row in eligible:
            identity = row["id"]
            if (student_predictions[identity] != row["gold"] and
                    predictions[identity] == row["gold"]):
                directed.add(identity)
    emitted = set()
    return tuple(
        row for row in rows
        if row["id"] in directed and
        (row["id"] not in emitted and not emitted.add(row["id"])))


def _confidence_guidance(mx, mentors, picked, config, answer_ids,
                         *, scope_size, teacher_distill, lesson_grade=None):
    """Gold-agreeing frozen logits are small, policy-shaped gradient advice."""
    if not mentors or teacher_distill <= 0 or any(
            row.get("answer_kind", "binary") != "binary" for row in picked):
        return None
    import numpy as np
    ids, lengths, labels = _learning_student_ops._make_batch(picked, config.get("context", 96))
    vote_logits = []
    row_capabilities = tuple(row.get("capability") for row in picked)
    if lesson_grade is None:
        first_capability = next(
            (capability for capability in row_capabilities
             if isinstance(capability, str) and capability), "")
        lesson_grade = first_capability.partition(".")[0]
    direct_capabilities = {
        capability for mentor in mentors
        for capability in mentor.get("capabilities", ())
    }
    for mentor in mentors:
        vocabulary = (mentor.get("vocab_size") or len(mentor["graph"]["tokens"]))
        if (max(answer_ids) >= vocabulary or
                any(max(row["tokens"]) >= vocabulary for row in picked)):
            continue
        logits = _runtime_mlx_parity.forward_arrays(mx, mentor["weights"], ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        mx.eval(logits)
        raw = np.asarray(logits)[:, :2]
        vote_logits.extend(
            (breadth, raw, mask)
            for breadth, mask in _mentor_vote_specs(
                mentor, row_capabilities, lesson_grade=lesson_grade,
                direct_capabilities=direct_capabilities)
        )
    target, influence = _learning_champion_confidence.vote_targets(vote_logits, labels,
                                     eligible_capabilities=scope_size,
                                     teacher_distill=teacher_distill)
    return (target, influence) if np.any(influence) else None


def _typed_confidence_guidance(mx, mentors, picked, config, *, scope_size,
                               teacher_distill, lesson_grade=None):
    """Source-gold-agreeing grade-soup/same-grade advice for typed heads.

    The trained student and the frozen mentors are distinct. Historical
    smaller-vocabulary soups participate only in heads their tokens support.
    """
    import numpy as np
    from bilqis_mlx.typed_answer_training import prepare_typed_batches
    if teacher_distill <= 0 or not mentors:
        return None
    batches = prepare_typed_batches(picked, config["answer_heads"])
    guidance = {}
    row_capability = {row["id"]: row["capability"] for row in picked}
    if lesson_grade is None:
        lesson_grade = picked[0]["capability"].partition(".")[0]
    direct_capabilities = {
        capability for mentor in mentors
        for capability in mentor.get("capabilities", ())
    }
    for kind, batch in batches.items():
        eligible = []
        batch_capabilities = tuple(
            row_capability[row_id] for row_id in batch["row_ids"])
        answer_ids = batch["answer_ids"]
        if not answer_ids:
            continue
        for mentor in mentors:
            vocabulary = mentor.get("vocab_size") or len(mentor["graph"]["tokens"])
            if (max(answer_ids) >= vocabulary or
                    int(batch["ids"].max()) >= vocabulary):
                continue
            logits = _runtime_mlx_parity.forward_arrays(
                mx, mentor["weights"], batch["ids"], batch["lengths"],
                heads=config["heads"], layers=config["layers"], answer_ids=answer_ids)
            mx.eval(logits)
            raw = np.asarray(logits)
            eligible.extend(
                (breadth, raw, mask)
                for breadth, mask in _mentor_vote_specs(
                    mentor, batch_capabilities, lesson_grade=lesson_grade,
                    direct_capabilities=direct_capabilities)
            )
        if not eligible:
            continue
        target, weight = _learning_champion_confidence.vote_targets_typed(
            eligible, batch["target_indices"], classes=len(answer_ids),
            eligible_capabilities=scope_size, teacher_distill=teacher_distill)
        if np.any(weight):
            guidance[kind] = (target, weight)
    return guidance or None
