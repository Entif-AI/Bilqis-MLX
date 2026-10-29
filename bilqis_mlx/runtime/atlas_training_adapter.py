"""Release-bound, source-visible BAMF input preparation.

The compiler and feature callables are explicit seams until A05 and A06 land.
They are the interfaces in their owner contracts, not replacement implementations.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from graphlib import CycleError, TopologicalSorter
from typing import Any, Callable

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.factory.adapters import validate_instructional_constituents
from bilqis_mlx.factory.generation import runtime_adapter_for_release
from bilqis_mlx.factory.teaching import DeliveredTeaching, describe_delivered_teaching, content_digest


@dataclass(frozen=True)
class BamfModelInput:
    prefix: Any
    features: tuple
    eligibility_digest: str
    answer_plan: tuple


@dataclass(frozen=True)
class BamfTarget:
    kind: str
    value: Any
    token_id: Any
    mask: bool | tuple[bool, ...]


@dataclass(frozen=True)
class BamfTargetEvidence:
    gold: Any
    answer_plan: Any
    auxiliary_labels: Any


@dataclass(frozen=True)
class BamfDeliveryProvenance:
    row_id: str
    source_id: str | None
    capability_id: str
    operation_id: str | None
    teacher_strategy: tuple
    requested_count: int
    delivered_count: int
    rehearsal: str | None
    optimizer_step_seed: int
    source_family_id: str | None = None
    episode_id: str | None = None


@dataclass(frozen=True)
class BamfTrainingRow:
    model_input: BamfModelInput
    target: BamfTarget
    native_target: BamfTarget | None
    provenance: BamfDeliveryProvenance
    auxiliaries: tuple = ()
    rule_policy: tuple = ()


@dataclass(frozen=True)
class BamfTrainingBatch:
    release_sha256: str
    generation_binding: str
    delivered_content_sha256: str
    rows: tuple[BamfTrainingRow, ...]


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_TRAINING_ADAPTER.INVALID, reason=reason)


def _freeze(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return tuple((key, _freeze(value[key])) for key in sorted(value))
    _invalid('UNSUPPORTED_SOURCE_OR_PROVENANCE_VALUE')


def _answer_plan(plan, head, visible_end, generation_binding):
    fields = {'modalityID', 'input_prefix_end', 'decisions', 'allowedOutputSchema',
              'maximum_decisions', 'generation_binding'}
    decision_fields = {'id', 'roleID', 'occurrence', 'kind', 'legalValues', 'depends_on'}
    if (not isinstance(plan, dict) or set(plan) != fields or plan['modalityID'] != head.modality_id
            or type(plan['input_prefix_end']) is not int or not 0 <= plan['input_prefix_end'] <= visible_end
            or type(plan['maximum_decisions']) is not int or not 1 <= plan['maximum_decisions'] <= 64
            or not isinstance(plan['decisions'], (list, tuple)) or not plan['decisions']
            or len(plan['decisions']) > plan['maximum_decisions']
            or not plan['allowedOutputSchema'] or plan['generation_binding'] != generation_binding):
        _invalid('ANSWER_PLAN_INVALID')
    graph = {}
    for decision in plan['decisions']:
        if (not isinstance(decision, dict) or set(decision) != decision_fields
                or not isinstance(decision['id'], str) or not decision['id']
                or not isinstance(decision['roleID'], str) or not decision['roleID']
                or type(decision['occurrence']) is not int or decision['occurrence'] < 0
                or decision['kind'] not in ('VALUE', 'ROLE', 'CONTROL', 'EPISTEMIC')
                or not isinstance(decision['legalValues'], (list, tuple)) or not decision['legalValues']
                or not isinstance(decision['depends_on'], (list, tuple))
                or any(not isinstance(dep, str) or not dep for dep in decision['depends_on'])
                or decision['id'] in graph):
            _invalid('ANSWER_PLAN_INVALID')
        graph[decision['id']] = tuple(decision['depends_on'])
    if any(dep not in graph for deps in graph.values() for dep in deps):
        _invalid('ANSWER_PLAN_INVALID')
    try:
        tuple(TopologicalSorter(graph).static_order())
    except CycleError:
        _invalid('ANSWER_PLAN_INVALID')
    return _freeze(plan)


def require_current_release(batch: BamfTrainingBatch, source_context: SourceExecutionContext, *,
                            generation_binding: str) -> None:
    """Refuse a prepared batch after its Factory release or semantic graph changes."""
    if not isinstance(batch, BamfTrainingBatch) or not isinstance(source_context, SourceExecutionContext):
        _invalid('SOURCE_CONTEXT_REQUIRED')
    source_context.release.verify()
    source_context.release.verify_semantic_catalog(source_context.graph)
    if (batch.release_sha256 != source_context.release.release_sha256 or
            not isinstance(generation_binding, str) or not generation_binding or
            batch.generation_binding != generation_binding):
        _invalid('STALE_FACTORY_RELEASE')


def compile_training_batch(delivered_rows, source_context: SourceExecutionContext,
                           topology, *, delivery: DeliveredTeaching, delivery_capability: str,
                           delivery_release_sha256: str, teacher_strategy: dict,
                           requested_count: int, optimizer_step_seed: int,
                           rehearsal_by_id: dict, visible_ends: dict,
                           source_ast_for: Callable, compile_prefix: Callable,
                           feature_requests_for: Callable, features_for: Callable, answer_plan_for: Callable,
                           frames_for_ast: Callable, check_context_eligibility: Callable,
                           eligible_source_for: Callable, task_scope, source_frontier,
                           eligibility_policy, generation_binding: str,
                           target_encoders: dict | None = None, sealed_holdout_ids=()) -> BamfTrainingBatch:
    """Compile source-oracled delivery using explicit frozen A05/A06 seams."""
    if not isinstance(source_context, SourceExecutionContext):
        _invalid('SOURCE_CONTEXT_REQUIRED')
    if not isinstance(delivered_rows, (tuple, list)) or not delivered_rows:
        _invalid('DELIVERED_ROWS_REQUIRED')
    if any(not callable(fn) for fn in (source_ast_for, compile_prefix, feature_requests_for, features_for,
                                           frames_for_ast, check_context_eligibility, eligible_source_for, answer_plan_for)):
        _invalid('UPSTREAM_INTERFACES_REQUIRED')
    source_context.release.verify()
    source_context.release.verify_semantic_catalog(source_context.graph)
    release = source_context.release
    capabilities = release.execution_plan.capability_map
    if (delivery_release_sha256 != release.release_sha256 or not isinstance(delivery, DeliveredTeaching)
            or delivery_capability not in capabilities):
        _invalid('DELIVERY_RELEASE_INVALID')
    try:
        expected = describe_delivered_teaching(release, delivery_capability, delivery.option_id, delivered_rows)
    except (ValueError, KeyError, TypeError):
        _invalid('DELIVERY_INVALID')
    if delivery != expected or len(delivery.specimen_ids) != len(delivered_rows):
        _invalid('DELIVERY_CONTENT_MISMATCH')
    if (type(requested_count) is not int or requested_count < len(delivered_rows)
            or type(optimizer_step_seed) is not int or optimizer_step_seed < 0
            or not isinstance(teacher_strategy, dict) or not isinstance(rehearsal_by_id, dict)
            or not isinstance(visible_ends, dict) or not isinstance(generation_binding, str) or not generation_binding
            or (target_encoders is not None and not isinstance(target_encoders, dict))):
        _invalid('DELIVERY_METADATA_INVALID')
    if (not isinstance(sealed_holdout_ids, (tuple, list, frozenset)) or
            any(not isinstance(identity, str) for identity in sealed_holdout_ids)):
        _invalid('HOLDOUT_IDENTITIES_INVALID')
    heads = {head.kind: head for head in release.answer_heads}
    result = []
    for row in delivered_rows:
        if not isinstance(row, dict):
            _invalid('ROW_INVALID')
        identity, capability = row.get('id'), row.get('capability')
        if not isinstance(identity, str) or not identity or not isinstance(capability, str) or capability not in capabilities:
            _invalid('ROW_IDENTITY_OR_CAPABILITY_INVALID')
        if identity in sealed_holdout_ids:
            _invalid('SEALED_HOLDOUT_IN_TRAINING')
        source_id, operation_id = row.get('source_id'), row.get('operation_id')
        family, episode = row.get('source_family_id'), row.get('episode_id')
        if any(value is not None and (not isinstance(value, str) or not value) for value in (family, episode)):
            _invalid('SOURCE_FAMILY_IDENTITY_INVALID')
        if operation_id is None and isinstance(row.get('record'), dict):
            operation_id = row['record'].get('operator')
        if ((source_id is not None and (not isinstance(source_id, str) or not source_id)) or
                (operation_id is not None and (not isinstance(operation_id, str) or not operation_id))):
            _invalid('SOURCE_OR_OPERATION_INVALID')
        owner = capabilities[delivery_capability]
        if delivery.option_id == 'source.direct/' + delivery_capability:
            if capability != delivery_capability:
                _invalid('DELIVERY_CAPABILITY_MISMATCH')
        elif (capability not in {delivery_capability, *owner.prerequisites}
              or capabilities[capability].provider_id != owner.provider_id
              or capabilities[capability].provider_implementation_sha256 != owner.provider_implementation_sha256):
            _invalid('DELIVERY_CAPABILITY_MISMATCH')
        adapter = runtime_adapter_for_release(source_context.source_root, source_context.graph, release,
                                              source_context.source_registry, capabilities[capability])
        if adapter.check(row, source_root=source_context.source_root, graph=source_context.graph,
                         course=release.curriculum) is not True:
            _invalid('SOURCE_ORACLE_REJECTED')
        validate_instructional_constituents(row, curriculum=release.curriculum, plan=release.execution_plan,
                                            capability=capability, adapter=adapter)
        rehearsal = rehearsal_by_id.get(identity)
        if rehearsal is not None and not isinstance(rehearsal, str):
            _invalid('REHEARSAL_INVALID')
        tokens = row.get('tokens')
        end = visible_ends.get(identity, len(tokens) if isinstance(tokens, (list, tuple)) else None)
        if (not isinstance(tokens, (list, tuple)) or type(end) is not int or end < 1 or end > len(tokens)
                or any(type(token) is not int or token < 0 or token >= len(source_context.graph['tokens'])
                       for token in tokens[:end])):
            _invalid('SOURCE_PREFIX_INVALID')
        kind, gold = row.get('answer_kind', 'binary'), row.get('gold')
        families = {family.kind: family.values for family in capabilities[capability].answer_families}
        if not isinstance(kind, str) or kind not in families or kind not in heads:
            _invalid('ANSWER_NOT_RELEASED')
        source_context.answer_registry.require(kind)
        head = heads[kind]
        visible = tuple(tokens[:end])
        ast = source_ast_for(visible)
        eligible = check_context_eligibility(frames_for_ast(ast), task_scope, source_frontier, eligibility_policy)
        try:
            eligible_ast, eligibility_digest = eligible_source_for(eligible)
        except (TypeError, ValueError):
            _invalid('CONTEXT_NOT_ELIGIBLE')
        if (not isinstance(eligibility_digest, str) or len(eligibility_digest) != 64
                or any(c not in '0123456789abcdef' for c in eligibility_digest)):
            _invalid('ELIGIBILITY_DIGEST_INVALID')
        prefix = compile_prefix(eligible_ast, len(visible), release, topology)
        queries = feature_requests_for(prefix)
        if not isinstance(queries, (list, tuple)) or any(not isinstance(q, (list, tuple)) or len(q) != 4 for q in queries):
            _invalid('FEATURE_REQUESTS_INVALID')
        features = tuple(_freeze(features_for(*query)) for query in queries)
        plan = _answer_plan(answer_plan_for(prefix, release, capabilities[capability], kind), head, len(visible), generation_binding)
        encoder = (target_encoders or {}).get(kind)
        if isinstance(gold, str) and (gold not in families[kind] or gold not in head.values):
            _invalid('ANSWER_NOT_RELEASED')
        if encoder is None:
            if not isinstance(gold, str) or gold not in families[kind] or gold not in head.values:
                _invalid('ANSWER_NOT_RELEASED')
            target = BamfTarget(kind, gold, head.token_ids[head.values.index(gold)], True)
        else:
            if not callable(encoder):
                _invalid('TARGET_ENCODER_INVALID')
            evidence = BamfTargetEvidence(_freeze(gold), plan,
                                          _freeze(row.get('auxiliary_labels')))
            encoded = encoder(evidence, head)
            if (not isinstance(encoded, BamfTarget) or encoded.kind != kind or
                    not (type(encoded.mask) is bool or isinstance(encoded.mask, tuple)
                         and all(type(mask) is bool for mask in encoded.mask))):
                _invalid('TARGET_ENCODER_INVALID')
            target = BamfTarget(kind, _freeze(encoded.value), _freeze(encoded.token_id), encoded.mask)
        native_target = None
        native = row.get('native_output')
        if kind.startswith('numeric_') and native is None:
            _invalid('NATIVE_TARGET_REQUIRED')
        if native is not None:
            if not isinstance(gold, str) or gold not in head.values:
                _invalid('NATIVE_TARGET_MISMATCH')
            native_token_id = head.token_ids[head.values.index(gold)]
            if (not isinstance(native, dict) or native.get('token_id') != native_token_id or
                    native.get('identity') != source_context.graph['tokens'][native_token_id]):
                _invalid('NATIVE_TARGET_MISMATCH')
            native_target = BamfTarget('semantic_token', native['identity'], native['token_id'], True)
        provenance = BamfDeliveryProvenance(identity, source_id, capability, operation_id,
            _freeze(teacher_strategy), requested_count, len(delivered_rows), rehearsal, optimizer_step_seed, family, episode)
        result.append(BamfTrainingRow(BamfModelInput(prefix, features, eligibility_digest, plan), target, native_target, provenance))
    return BamfTrainingBatch(release.release_sha256, generation_binding, content_digest(delivered_rows), tuple(result))


@dataclass(frozen=True)
class PaddedMicrobatch:
    row_indices: tuple[int, ...]
    positions: tuple
    padding_mask: tuple


def pad_microbatches(batch, topology, memory_budget, *, plan_microbatches, indices_for_plan, positions_for):
    """Consume C08's partition; preserve every logical row and actual lengths."""
    plan = plan_microbatches(batch.rows, topology, memory_budget)
    groups = tuple(tuple(group) for group in indices_for_plan(plan))
    flattened = tuple(index for group in groups for index in group)
    if (not groups or any(not group for group in groups) or
            any(type(index) is not int for index in flattened) or
            flattened != tuple(range(len(batch.rows)))):
        _invalid('MICROBATCH_PARTITION_INVALID')
    result = []
    for group in groups:
        rows = tuple(tuple(positions_for(batch.rows[index].model_input.prefix)) for index in group)
        if any(not row or len(row) + dict(batch.rows[index].model_input.answer_plan)['maximum_decisions'] > 1024
               for index, row in zip(group, rows)):
            _invalid('COMPILED_CONTEXT_INVALID')
        width = max(map(len, rows))
        result.append(PaddedMicrobatch(group,
            tuple(row + (None,) * (width - len(row)) for row in rows),
            tuple((True,) * len(row) + (False,) * (width - len(row)) for row in rows)))
    return tuple(result)


def attach_auxiliaries(batch, evidence_by_row, *, verify):
    """Keep absent labels absent; require the source/outcome owner's verification."""
    known = {row.provenance.row_id for row in batch.rows}
    if not isinstance(evidence_by_row, dict) or not set(evidence_by_row) <= known:
        _invalid('AUXILIARY_EVIDENCE_INVALID')
    result = []
    for row in batch.rows:
        labels = evidence_by_row.get(row.provenance.row_id, {})
        if not isinstance(labels, dict):
            _invalid('AUXILIARY_EVIDENCE_INVALID')
        targets = []
        for name, evidence in sorted(labels.items()):
            if (name not in {'role', 'epistemic_state', 'impact', 'exigency', 'novelty', 'frame_atomic_consistency'}
                    or not isinstance(evidence, (tuple, list)) or len(evidence) != 3):
                _invalid('AUXILIARY_EVIDENCE_INVALID')
            value, regime, receipt = evidence
            if regime not in ('SOURCE', 'OUTCOME') or not receipt or verify(row.provenance.row_id, name, value, regime, receipt) is not True:
                _invalid('AUXILIARY_EVIDENCE_UNVERIFIED')
            targets.append((name, _freeze(value), regime, _freeze(receipt)))
        result.append(replace(row, auxiliaries=tuple(targets)))
    return replace(batch, rows=tuple(result))


def execute_with_backend(batch, source_context, topology, *, generation_binding, training, model_backend, invoke):
    """Use B11's single selector; inference receives no gold or auxiliary targets."""
    require_current_release(batch, source_context, generation_binding=generation_binding)
    if type(training) is not bool:
        _invalid('EXECUTION_MODE_INVALID')
    backend = model_backend(topology)
    inputs = tuple(row.model_input for row in batch.rows)
    targets = tuple((row.target, row.native_target, row.auxiliaries) for row in batch.rows) if training else None
    return invoke(backend, inputs, targets)


def capture_realized_delivery(batch, source_context, capture, capability, step, rows, *,
                              generation_binding, option_rows, priority, preservation, support,
                              enrichment, guidance, controls, seed, cost, prior=(), mentors=None):
    """Forward actual delivery and measured cost to the existing #333 owner."""
    from bilqis_mlx.factory.teaching import content_digest
    require_current_release(batch, source_context, generation_binding=generation_binding)
    if (type(step) is not int or step < 1 or content_digest(rows) != batch.delivered_content_sha256
            or tuple(row.get('id') for row in rows) != tuple(row.provenance.row_id for row in batch.rows)
            or not isinstance(controls, dict) or 'realized_cost' in controls
            or not isinstance(cost, dict) or not cost):
        _invalid('OBSERVATION_DELIVERY_INVALID')
    capture.delivery(source_context.release, capability, step, rows, option_rows=option_rows,
        priority=priority, preservation=preservation, support=support, enrichment=enrichment,
        guidance=guidance, controls={**controls, 'realized_cost': cost,
                                    'delivered_content_sha256': content_digest(rows)},
        seed=seed, prior=prior, mentors=mentors)


def require_independent_cohorts(training, holdout):
    """Refuse missing provenance and known family/episode siblings as independent."""
    def identities(batch):
        families, episodes = set(), set()
        for row in batch.rows:
            family, episode = row.provenance.source_family_id, row.provenance.episode_id
            if not family or not episode:
                _invalid('SOURCE_INDEPENDENCE_NOT_MEASURED')
            families.add(family)
            episodes.add(episode)
        return families, episodes
    train_families, train_episodes = identities(training)
    test_families, test_episodes = identities(holdout)
    if train_families & test_families or train_episodes & test_episodes:
        _invalid('SOURCE_FAMILY_LEAK')


def resolve_batch_rules(batch, source_context, *, released_signatures_for, rule_set_for):
    """Dispatch source-domain rules from released signatures without grade metadata."""
    require_current_release(batch, source_context, generation_binding=batch.generation_binding)
    release = source_context.release
    result = []
    for row in batch.rows:
        family = row.provenance.source_family_id
        if not family:
            _invalid('RULE_SOURCE_FAMILY_REQUIRED')
        capability = release.curriculum.capability_map[row.provenance.capability_id]
        binding = release.source_bindings.by_capability[row.provenance.capability_id]
        signatures = _freeze(released_signatures_for(release, source_context.graph, capability.taught_roots))
        if not signatures:
            _invalid('RELEASED_SIGNATURES_REQUIRED')
        policy = _freeze(rule_set_for(binding.source_anchor, signatures, family))
        if not isinstance(policy, tuple) or not policy:
            _invalid('SOURCE_RULE_POLICY_REQUIRED')
        result.append(replace(row, rule_policy=policy))
    return replace(batch, rows=tuple(result))
