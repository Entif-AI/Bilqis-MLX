"""Structural extraction from reconciliation.py; behavior preserved."""
from __future__ import annotations
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import dataclasses as _dataclasses

_IDENTICAL_OPT_IN_REQUIRED = "LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN"

def _reconcile_vocabulary_metadata(run_dir, receipt, course, parameters,
                                   optimizer, graph):
    """Repair historical stale size metadata by a NEW immutable generation.

    A bound checkpoint's source-verified graph and embedding tensor, not the
    initial inherited model config, own the current active vocabulary size.
    Historical 222-token prefix evidence and previously saved states survive.
    """
    actual = len(graph["tokens"])
    embedded = int(parameters["embedding.weight"].shape[0])
    if actual != embedded or actual < 1:
        raise ValueError("HUMAN_TRAINER_CURRENT_VOCAB_GRAPH_EMBEDDING_DRIFT")
    native = receipt["config"].get("answer_heads", {}).get("semantic_token")
    if native is not None and (
            len(native["token_ids"]) != actual or
            native["token_ids"] != list(range(actual))):
        raise ValueError("HUMAN_TRAINER_CURRENT_VOCAB_ANSWER_HEAD_DRIFT")
    previous = receipt["config"].get("vocab_size")
    if previous == actual:
        return receipt
    if type(previous) is not int or previous < 1 or previous > actual:
        raise ValueError("HUMAN_TRAINER_UNVERIFIED_VOCAB_METADATA_MIGRATION")
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("HUMAN_TRAINER_VOCAB_RECONCILE_OWN_ADAMW_DRIFT")
    candidate = _runtime_checkpoints._advance(
        run_dir, {**receipt, "config": {**receipt["config"], "vocab_size": actual}},
        school, persist=False)
    event = {"event": "SCHOOL_CURRENT_VOCAB_METADATA_RECONCILED",
             "generation": candidate["generation"],
             "former_metadata_vocab_size": previous,
             "active_semantic_graph_vocab_size": actual,
             "student_sha256": school.current_student.sha256,
             "optimizer_step": school.current_student.optimizer_step,
             "model_and_optimizer_unchanged": True}
    result = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(candidate, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, result)
    return result

def _reconcile_learning_settings(run_dir, receipt, course, settings, optimizer):
    """Permit only narrower existing retention budgets on human resume.

    Previously selected strategy outcomes keep their historic settings. The
    full student and its AdamW are unchanged by this metadata-only boundary.
    An attempted loosening or an unreviewed probe redesign still fails closed.
    """
    inherited = receipt.get("learning_experiment")
    if inherited is None:
        return receipt
    if settings is None or inherited.get("version") != _learning_learning_experiment.VERSION:
        raise ValueError(_IDENTICAL_OPT_IN_REQUIRED)
    new = _dataclasses.asdict(settings)
    previous = inherited.get("settings")
    if previous == new:
        return receipt
    if not isinstance(previous, dict):
        raise ValueError("LEARNING_EXPERIMENT_HISTORY_INVALID")
    old = _dataclasses.asdict(_learning_learning_experiment.Settings(**previous))
    if (new["probe_each"] != old["probe_each"] or
            new["protected_cap_limit"] != old["protected_cap_limit"] or
            new["introduction_extra_loss"] != old["introduction_extra_loss"] or
            new["mature_max_loss"] >= old["mature_max_loss"]):
        raise ValueError(_IDENTICAL_OPT_IN_REQUIRED)
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("LEARNING_EXPERIMENT_POLICY_OWN_ADAMW_DRIFT")
    prior = list(receipt.get("learning_policy_revisions", ()))
    change = {"from": old, "to": new,
              "from_generation": receipt["generation"],
              "optimizer_step": school.current_student.optimizer_step,
              "student_sha256": school.current_student.sha256}
    candidate = _runtime_checkpoints._advance(run_dir, {**receipt,
        "learning_experiment": {"version": _learning_learning_experiment.VERSION,
                                "settings": new},
        "learning_policy_revisions": [*prior, change]}, school, persist=False)
    event = {"event": "SCHOOL_EXPERIMENTAL_RETENTION_POLICY_TIGHTENED",
             "generation": candidate["generation"], **change,
             "model_and_optimizer_unchanged": True}
    result = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(candidate, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, result)
    return result
