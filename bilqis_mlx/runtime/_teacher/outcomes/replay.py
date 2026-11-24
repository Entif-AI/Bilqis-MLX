"""Fold B13-authenticated current-parent rejection credit before HOW selection."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

from bilqis_mlx.learning.teacher_strategy_population import LEGACY_CHECKPOINT_RETIREMENT_POLICY
from bilqis_mlx.runtime.priority_rejection_replay import current_rejection_outcomes
from bilqis_mlx.runtime.state import _fingerprint

from .observations import (
    _compact_selected_teacher, invalid, ledger,
)



def _factory_capability_count(run_dir, observation):
    digest = observation["context"]["factory_release_sha256"]
    receipt = {
        "factory_release_sha256": digest,
        "factory_release_file": f"factory-releases/{digest}.json",
    }
    from bilqis_mlx.runtime.admission import _read_executable_factory_release_artifact
    release = _read_executable_factory_release_artifact(Path(run_dir), receipt)
    capabilities = release.execution_plan.capabilities
    if (release.release_sha256 != digest or type(capabilities) is not tuple
            or not capabilities):
        invalid()
    return len(capabilities)


def _selection_capability_count(run_dir, observation):
    total = observation["context"].get("total_capabilities")
    if total is None:
        return _factory_capability_count(run_dir, observation)
    if type(total) is not int or total < 1:
        invalid()
    return total


def _recorded_diagnostic_context(selected, observation):
    from bilqis_mlx.learning._learning_experiment_decision import (
        DIAGNOSTIC_CONTEXT_KEY_LENGTH, _channel,
    )
    context = observation["context"]
    key, diagnostics = (
        context.get("diagnostic_context_key"), context.get("diagnostics"))
    if (not isinstance(key, str)
            or len(key) != DIAGNOSTIC_CONTEXT_KEY_LENGTH
            or not isinstance(diagnostics, dict)
            or hashlib.sha256(
                json.dumps(diagnostics, sort_keys=True).encode()
            ).hexdigest()[:DIAGNOSTIC_CONTEXT_KEY_LENGTH] != key):
        invalid()
    channel = _channel(selected)
    contexts = channel.setdefault("diagnostic_contexts", {})
    previous = contexts.get(key)
    if previous is not None and previous != diagnostics:
        invalid()
    contexts[key] = deepcopy(diagnostics)
    return channel, key


def _recover_mutated_selected_teacher(run_dir, teacher, observation):
    """Replay one recorded fresh teacher mutation and require its exact hash."""
    from bilqis_mlx.compatibility import historical_teacher_policy
    from bilqis_mlx.learning import _learning_experiment_policy as experiment
    import bilqis_mlx.learning.teacher_breeding as breeding
    import bilqis_mlx.learning.teacher_strategy_population as population

    selected = deepcopy(teacher)
    channel, diagnostic_key = _recorded_diagnostic_context(
        selected, observation)
    context, visit = observation["context"], observation["teacher_visit"]
    checkpoint_retirement_policy = context.get(
        "checkpoint_retirement_policy", LEGACY_CHECKPOINT_RETIREMENT_POLICY)
    capability = visit["capability_id"]
    phase = context["phase"]
    scope_name = context["curriculum_scope"]
    grade = context["grade"]
    total_capabilities = _selection_capability_count(run_dir, observation)
    context_key = capability + "|" + phase + "|" + scope_name
    scope = channel["contexts"].get(context_key, {})
    active, inventory, _retired = breeding.selection_population(
        selected, grade=grade, capability=capability,
        curriculum_scope=scope_name, scope=scope, channel=channel,
        context_key=context_key,
        student_checkpoint_sha256=visit["student_sha256"],
        total_capabilities=total_capabilities,
        checkpoint_retirement_policy=checkpoint_retirement_policy)
    active_set = set(active)
    effective_scope = {
        key: record
        for key, record in experiment._effective_context_scope(
            selected, scope).items()
        if key in active_set
    } if scope else {}
    rejection_pressure = int(experiment._capability_stagnation(
        channel, capability, scope_name).get("rejection_streak", 0))
    if (rejection_pressure < experiment.BESPOKE_EXPLORATION_START
            or any(int(record.get("retained", 0)) > 0
                   for record in effective_scope.values())):
        invalid()
    challenger = breeding.pressure_challenger(
        historical_teacher_policy, selected,
        random.Random(visit["selection_seed"]),
        capability=capability, phase=phase, curriculum_scope=scope_name,
        diagnostic_key=diagnostic_key,
        total_capabilities=total_capabilities)
    if challenger is None:
        invalid()
    key, policy, reason, _detail = challenger
    if reason != "FRESH_MUTATED_CHALLENGER":
        invalid()

    # Mirror the state-mutating population pass performed by
    # runtime.teacher_policy_selection after contextual selection.
    scope = channel.get("contexts", {}).get(context_key, {})
    active, inventory = population.active_effective_strategy_keys(
        selected, grade, scope, total_capabilities=total_capabilities)
    active = breeding.filter_active_effective(
        selected, grade=grade, capability=capability,
        curriculum_scope=scope_name, active_effective=active,
        inventory=inventory)
    population.checkpoint_active_effective_strategy_keys(
        selected, grade, scope, channel, context_key, active, inventory,
        visit["student_sha256"],
        checkpoint_retirement_policy=checkpoint_retirement_policy)

    if (key != visit["policy_key"]
            or policy != observation["selected_policy"]
            or _fingerprint(selected)
            != observation.get("selected_teacher_sha256")):
        invalid()
    return selected


def _recover_checkpointed_selected_teacher(run_dir, teacher, observation):
    """Replay deterministic active-population checkpointing from policy selection."""
    import bilqis_mlx.learning.teacher_breeding as breeding
    import bilqis_mlx.learning.teacher_strategy_population as population

    selected = deepcopy(teacher)
    context, visit = observation["context"], observation["teacher_visit"]
    checkpoint_retirement_policy = context.get(
        "checkpoint_retirement_policy", LEGACY_CHECKPOINT_RETIREMENT_POLICY)
    capability = visit["capability_id"]
    scope_name = context["curriculum_scope"]
    grade = context["grade"]
    channel = selected.get("causal_experiment", {})
    context_key = capability + "|" + context["phase"] + "|" + scope_name
    scope = channel.get("contexts", {}).get(context_key, {})
    total_capabilities = _selection_capability_count(run_dir, observation)
    active, inventory = population.active_effective_strategy_keys(
        selected, grade, scope, total_capabilities=total_capabilities)
    active = breeding.filter_active_effective(
        selected, grade=grade, capability=capability,
        curriculum_scope=scope_name, active_effective=active,
        inventory=inventory)
    population.checkpoint_active_effective_strategy_keys(
        selected, grade, scope, channel, context_key, active, inventory,
        visit["student_sha256"],
        checkpoint_retirement_policy=checkpoint_retirement_policy)
    if (_fingerprint(selected) == observation.get("selected_teacher_sha256")
            and selected.get("strategies", {}).get(visit["policy_key"])
            == observation.get("selected_policy")):
        return selected
    return None


def _selected_teacher_override(run_dir, teacher, observation):
    if "selected_teacher" in observation:
        return None
    visit = observation["teacher_visit"]
    prior = ledger(teacher, visit["accepted_manifest_sha256"])
    applied = prior["applied"].get(observation["attempt_id"])
    if applied == observation.get("outcome_sha256"):
        return None
    if applied is not None:
        invalid()
    selected_sha256 = observation.get("selected_teacher_sha256")
    compact = _compact_selected_teacher(teacher, observation["context"])
    if (isinstance(selected_sha256, str)
            and _fingerprint(compact) == selected_sha256):
        return None
    checkpointed = _recover_checkpointed_selected_teacher(
        run_dir, teacher, observation)
    if checkpointed is not None:
        return checkpointed
    return _recover_mutated_selected_teacher(run_dir, teacher, observation)


def replay_rejected_outcomes(run_dir, parent, cache, teacher):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import strict_mode_enabled
    from .replay_fold import fold_rejections
    from .replay_cache import replay_ordinary

    rows = current_rejection_outcomes(run_dir, parent, cache)
    def fold(base, tail):
        return fold_rejections(run_dir, cache, base, tail, _selected_teacher_override)
    if strict_mode_enabled():
        return fold(teacher, rows)
    return replay_ordinary(run_dir, cache, teacher, rows, fold)
