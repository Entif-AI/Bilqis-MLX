"""Disposable Factory source owner for the C13.1 episode-binding witness."""
from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

from bilqis_mlx.curriculum import AnswerFamily
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
    merge_prefix_domain,
)
from bilqis_mlx.factory.curriculum_definition import (
    CapabilitySourceBinding, CapabilitySpec, CurriculumDefinition, GradeSpec,
    SourceBindingSet,
)
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, SourceKind, SourceOperand, TypedValue, default_registry,
    operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.source_adapters.task_goal_registry import RegisteredTaskGoalLowerer

from scripts.bamf.c13_episode_fixtures import (
    EpisodeBindingCase, EpisodeEvent, check_episode_binding, episode_binding_case,
    episode_task_goal,
)

CAPABILITY = "Z.C13_EPISODE"
PROVIDER_ID = "source.bamf.c13.episode-binding/v1"
GENERATOR_ID = "bilqis.c13.episode-binding-generator/v1"
ORACLE_ID = "bilqis.c13.episode-binding-checker/v1"
LOWERER_ID = "bilqis.c13.episode-binding-task-goal/v1"
SOURCE_FAMILY = "bamf.c13.episode-binding/v1"
NUMBER_VALUES = tuple(str(index) for index in range(21))
_NUMBER_TOKENS = tuple("school.number." + value for value in NUMBER_VALUES)
_SYMBOLS = (
    "c13.actor.A", "c13.actor.B", "c13.actor.C", "c13.event.0", "c13.event.1",
    "c13.relation.successor", "c13.query.later-duration", "c13.query.sum-durations",
)


def implementation_digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def episode_graph() -> dict:
    return {"tokens": ["fixture.padding", *_NUMBER_TOKENS, *_SYMBOLS]}


def _case_from_record(record: dict) -> EpisodeBindingCase:
    return EpisodeBindingCase(
        record["seed"], record["depth"],
        tuple(EpisodeEvent(**event) for event in record["events"]),
        record["relation_cue"]["from_actor"], record["query"])


def _tokens(case: EpisodeBindingCase, graph: dict) -> list[int]:
    ids = {token: index for index, token in enumerate(graph["tokens"])}
    result = []
    for event in case.events:
        result.extend((
            ids["c13.actor." + event.actor], ids["c13.event." + str(event.ordinal)],
            ids["school.number." + str(event.duration_minutes)],
        ))
    result.extend((
        ids["c13.actor." + case.cue_actor], ids["c13.relation.successor"],
        ids["school.number." + str(case.depth)],
        ids["c13.query." + (
            "later-duration" if case.query_kind == "LATER_DURATION" else "sum-durations")],
    ))
    return result


def draw_episode(source_root, graph, *, seed, each=12, capability=CAPABILITY, **_) -> tuple[dict, ...]:
    del source_root
    if capability != CAPABILITY:
        raise ValueError("BAMF_C13_EPISODE_CAPABILITY_INVALID")
    rows = []
    for index in range(each):
        case = episode_binding_case(seed * 1000 + index, 1)
        record = case.source_view()
        row_id = contract_digest((GENERATOR_ID, record))
        rows.append({
            "id": row_id, "source_id": row_id, "capability": CAPABILITY,
            "answer_kind": "numeric_active", "gold": str(check_episode_binding(case)),
            "record": record, "tokens": _tokens(case, graph),
            "generator": GENERATOR_ID, "oracle": ORACLE_ID,
            "source_family_id": SOURCE_FAMILY, "episode_id": row_id,
        })
    return tuple(rows)


def check_episode_row(row: dict, **_) -> bool:
    try:
        case = _case_from_record(row["record"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        row.get("generator") == GENERATOR_ID
        and row.get("oracle") == ORACLE_ID
        and row.get("capability") == CAPABILITY
        and row.get("answer_kind") == "numeric_active"
        and row.get("gold") == str(check_episode_binding(case))
    )


def _grant(handle, evidence, release):
    return SourceGrant(
        handle, "bamf-c13", "bamf-c13", PUBLIC_FORMAL, release, evidence,
        ("C04_SOLVER",), ("LOCAL",), (CAPABILITY,), 1, 1, 0, 0)


def lower_episode_task_goal(row: dict, *, semantic_release: str, capability, **_):
    if "gold" in row or row.get("capability") != CAPABILITY:
        raise ValueError("BAMF_C13_TASK_SOURCE_VIEW_INVALID")
    case = _case_from_record(row["record"])
    goal = episode_task_goal(case, semantic_release)
    registry = default_registry(semantic_release)
    task = TaskScope(
        "bamf-c13", "bamf-c13", "C04_SOLVER", semantic_release, "LOCAL",
        CAPABILITY, 0, 0, len(row["tokens"]))
    policy = ContextPolicy(
        "bamf-c13-episode/v1", 1, 1, ("C04_SOLVER",), (PUBLIC_FORMAL,),
        ("LOCAL",), (CAPABILITY,), (PUBLIC_FORMAL,), (), ())
    operands = []
    grants = []
    for event in case.events:
        handle = f"source:c13:{case.seed}:duration:{event.actor}:{event.ordinal}"
        typed = TypedValue("Number", event.duration_minutes, semantic_release, handle)
        source = SourceOperand(typed, SourceKind.TASK_VISIBLE, row["source_id"], len(row["tokens"]))
        operands.append(source)
        grants.append(_grant(handle, source_operand_digest(source), semantic_release))
    for operator in goal.allowed_operator_ids:
        spec = registry.resolve(operator)
        grants.append(_grant(
            "source:operator:" + operator, operator_grant_digest(spec), semantic_release))
    binding = OperatorBinding(
        task, SourceFrontier(1, 1, tuple(sorted(grants, key=lambda item: item.source_handle))),
        policy, registry, tuple(operands))
    return goal, binding


def _target_actor(case: EpisodeBindingCase) -> str:
    first = {event.actor: event.start_minute for event in case.events if event.ordinal == 0}
    ordered = tuple(sorted(("A", "B", "C"), key=lambda actor: (first[actor], actor)))
    return ordered[(ordered.index(case.cue_actor) + case.depth) % len(ordered)]


def resolve_episode_task_goal(row: dict, *, semantic_release: str, capability, **kwargs):
    source = dict(row)
    source.pop("gold", None)
    goal, _binding = lower_episode_task_goal(
        source, semantic_release=semantic_release, capability=capability, **kwargs)
    case = _case_from_record(row["record"])
    target = _target_actor(case)
    nodes = []
    for node in goal.expression_or_holes.nodes:
        if node.node_id.startswith("select-"):
            ordinal = 1 if node.node_id == "select-later-duration" else 0
            handle = f"source:c13:{case.seed}:duration:{target}:{ordinal}"
            selected = tuple(ref for ref in node.candidate_operand_refs[0]
                             if ref.source_handle == handle)
            if len(selected) != 1:
                raise ValueError("BAMF_C13_TASK_TARGET_INVALID")
            node = replace(
                node, operands=(selected[0],), candidate_operand_refs=(), constraints=())
        nodes.append(node)
    return replace(goal, expression_or_holes=replace(goal.expression_or_holes, nodes=tuple(nodes)))


def registered_episode_adapter() -> RegisteredSourceAdapter:
    return RegisteredSourceAdapter(
        SourceAdapter(
            PROVIDER_ID, GENERATOR_ID, (ORACLE_ID,), implementation_digest(),
            variation_axes=("source-valid", "fresh-seed", "actor-binding", "query-form")),
        draw_episode, check_episode_row,
        semantic_footprint=lambda _row: ("c13.episode.binding",))


def registered_episode_lowerer() -> RegisteredTaskGoalLowerer:
    digest = implementation_digest()
    return RegisteredTaskGoalLowerer(
        PROVIDER_ID, digest, LOWERER_ID, digest,
        lower_episode_task_goal, resolve_episode_task_goal)


def episode_factory_release():
    curriculum = CurriculumDefinition(
        "bilqis.c13.episode-curriculum/v1",
        (GradeSpec("Z", (CapabilitySpec(
            CAPABILITY, "c13-disposable", ("c13.episode.binding",),
            ("c13.episode.binding",), (), (),
            (AnswerFamily("numeric_active", NUMBER_VALUES),)),),
            ((CAPABILITY, 12),), ((CAPABILITY,),)),),
        program_complete=True)
    bindings = SourceBindingSet((CapabilitySourceBinding(
        CAPABILITY, "public-formal:c13-episode-fixture", GENERATOR_ID, ORACLE_ID),),
        source_attestation_sha256="c" * 64)
    sources = SourceAdapterRegistry((registered_episode_adapter(),))
    answers = AnswerModalityRegistry((RegisteredAnswerModality(
        AnswerModality("numeric_active", "answer.numeric-active/v1", "d" * 64),
        merge_prefix_domain, lambda value: "school.number." + value),))
    graph = episode_graph()
    release = compile_executable_factory_release(
        curriculum, bindings, CurriculumProfile.full(), sources, answers,
        source_root=None, graph=graph, verification_seed=52813)
    return release, graph, sources, answers


__all__ = (
    "CAPABILITY", "check_episode_row", "draw_episode", "episode_factory_release",
    "episode_graph", "implementation_digest", "lower_episode_task_goal",
    "registered_episode_adapter", "registered_episode_lowerer",
    "resolve_episode_task_goal",
)
