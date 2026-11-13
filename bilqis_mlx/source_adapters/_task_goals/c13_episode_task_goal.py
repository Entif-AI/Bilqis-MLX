"""Gold-blind C04 lowering for the admitted C13 episode-binding source family."""
from __future__ import annotations

from dataclasses import replace

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, DAGProgram, RefKind, TaskGoal,
)
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, SourceKind, SourceOperand, TypedValue, default_registry,
    operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)

from bilqis_mlx.source_adapters.c13_episode import CAPABILITY
from bilqis_mlx.source_adapters.c13_episode_cases import (
    ACTORS, EpisodeBindingCase, case_from_record,
)


_PURPOSE = "C04_SOLVER"
_PRINCIPAL = "bamf-c13"
_TENANT = "bamf-c13"
_JURISDICTION = "LOCAL"


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


def _duration_ref(case: EpisodeBindingCase, actor: str, ordinal: int) -> DAGOperand:
    return DAGOperand(
        RefKind.LITERAL,
        "Number",
        source_handle=f"source:c13:{case.seed}:duration:{actor}:{ordinal}",
    )


def _task_goal(
    case: EpisodeBindingCase, semantic_release: str, goal_id: str,
) -> TaskGoal:
    later = tuple(_duration_ref(case, actor, 1) for actor in ACTORS)
    select_later = DAGNode(
        "select-later-duration",
        "SELECT_NUMBER",
        (None,),
        "Number",
        CAPABILITY,
        candidate_operand_refs=(later,),
        constraints=("SOURCE_VISIBLE", "TYPE_COMPATIBLE"),
    )
    nodes = [select_later]
    if case.query_kind == "SUM_DURATIONS":
        earlier = tuple(_duration_ref(case, actor, 0) for actor in ACTORS)
        select_earlier = DAGNode(
            "select-earlier-duration",
            "SELECT_NUMBER",
            (None,),
            "Number",
            CAPABILITY,
            candidate_operand_refs=(earlier,),
            constraints=("SOURCE_VISIBLE", "TYPE_COMPATIBLE"),
        )
        nodes = [
            select_earlier,
            select_later,
            DAGNode(
                "sum-visible-durations",
                "ADD",
                (
                    DAGOperand(
                        RefKind.RESULT, "Number",
                        result_node_id="select-earlier-duration"),
                    DAGOperand(
                        RefKind.RESULT, "Number",
                        result_node_id="select-later-duration"),
                ),
                "Number",
                CAPABILITY,
            ),
        ]
    visible = tuple(sorted({
        ref.identity
        for node in nodes
        for group in node.candidate_operand_refs
        for ref in group
    }))
    operators = tuple(sorted({node.operator_id for node in nodes if node.operator_id}))
    return TaskGoal(
        goal_id,
        "Number",
        visible,
        DAGProgram(tuple(nodes), nodes[-1].node_id, CAPABILITY),
        operators,
        DAGBudget(max_nodes=3, max_depth=3, max_operations=3, max_decisions=2),
        semantic_release,
        CAPABILITY,
    )


def _grant(handle, evidence, semantic_release):
    return SourceGrant(
        handle, _PRINCIPAL, _TENANT, PUBLIC_FORMAL, semantic_release, evidence,
        (_PURPOSE,), (_JURISDICTION,), (CAPABILITY,), 1, 1, 0, 0,
    )


def lower_c13_episode_task_goal(
    row: dict, *, semantic_release: str, capability, **_,
):
    if (not isinstance(row, dict) or "gold" in row
            or row.get("capability") != CAPABILITY
            or getattr(capability, "capability_id", None) != CAPABILITY):
        _invalid("BAMF_C13_TASK_SOURCE_VIEW_INVALID")
    try:
        case = case_from_record(row["record"])
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C13_TASK_SOURCE_VIEW_INVALID")
    goal_id = row.get("id")
    if not isinstance(goal_id, str) or not goal_id:
        _invalid("BAMF_C13_TASK_SOURCE_VIEW_INVALID")
    goal = _task_goal(case, semantic_release, goal_id)
    registry = default_registry(semantic_release)
    task = TaskScope(
        _PRINCIPAL, _TENANT, _PURPOSE, semantic_release, _JURISDICTION,
        CAPABILITY, 0, 0, len(row.get("tokens", ())),
    )
    policy = ContextPolicy(
        "bamf-c13-episode/v1", 1, 1, (_PURPOSE,), (PUBLIC_FORMAL,),
        (_JURISDICTION,), (CAPABILITY,), (PUBLIC_FORMAL,), (), (),
    )
    operands = []
    grants = []
    source_identity = str(row.get("source_id") or row.get("id") or "c13-row")
    for event in case.events:
        handle = f"source:c13:{case.seed}:duration:{event.actor}:{event.ordinal}"
        typed = TypedValue("Number", event.duration_minutes, semantic_release, handle)
        source = SourceOperand(
            typed, SourceKind.TASK_VISIBLE, source_identity, len(row.get("tokens", ())))
        operands.append(source)
        grants.append(_grant(handle, source_operand_digest(source), semantic_release))
    for operator in goal.allowed_operator_ids:
        grants.append(_grant(
            "source:operator:" + operator,
            operator_grant_digest(registry.resolve(operator)),
            semantic_release,
        ))
    binding = OperatorBinding(
        task,
        SourceFrontier(1, 1, tuple(sorted(grants, key=lambda item: item.source_handle))),
        policy,
        registry,
        tuple(operands),
    )
    return goal, binding


def _target_actor(case: EpisodeBindingCase) -> str:
    first = {
        event.actor: event.start_minute
        for event in case.events if event.ordinal == 0
    }
    ordered = tuple(sorted(ACTORS, key=lambda actor: (first[actor], actor)))
    return ordered[(ordered.index(case.cue_actor) + case.depth) % len(ordered)]


def resolve_c13_episode_task_goal(
    row: dict, *, semantic_release: str, capability, **kwargs,
):
    if not isinstance(row, dict):
        _invalid("BAMF_C13_TASK_TARGET_INVALID")
    source = dict(row)
    source.pop("gold", None)
    goal, _binding = lower_c13_episode_task_goal(
        source, semantic_release=semantic_release, capability=capability, **kwargs)
    try:
        case = case_from_record(row["record"])
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C13_TASK_TARGET_INVALID")
    target = _target_actor(case)
    nodes = []
    for node in goal.expression_or_holes.nodes:
        if node.node_id.startswith("select-"):
            ordinal = 1 if node.node_id == "select-later-duration" else 0
            handle = f"source:c13:{case.seed}:duration:{target}:{ordinal}"
            selected = tuple(
                ref for ref in node.candidate_operand_refs[0]
                if ref.source_handle == handle
            )
            if len(selected) != 1:
                _invalid("BAMF_C13_TASK_TARGET_INVALID")
            node = replace(
                node, operands=(selected[0],), candidate_operand_refs=(), constraints=())
        nodes.append(node)
    return replace(
        goal,
        expression_or_holes=replace(goal.expression_or_holes, nodes=tuple(nodes)),
    )


__all__ = (
    "lower_c13_episode_task_goal", "resolve_c13_episode_task_goal",
)
