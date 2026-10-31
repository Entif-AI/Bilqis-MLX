"""Release-bound, source-visible BAMF input preparation.

The compiler and feature callables are explicit seams until A05 and A06 land.
They are the interfaces in their owner contracts, not replacement implementations.
"""
from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from typing import Callable

from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.factory.adapters import validate_instructional_constituents
from bilqis_mlx.factory.generation import runtime_adapter_for_release
from bilqis_mlx.factory.teaching import DeliveredTeaching, describe_delivered_teaching, content_digest
from bilqis_mlx.semantics.context_eligibility import (
    ContextEligibility, ContextPolicy, EligibleContext, SourceFrontier,
    TaskScope, check_context_eligibility as _check_context_eligibility,
)
from .atlas_training_contracts import (
    BamfModelInput, BamfTarget, BamfTargetEvidence, BamfDeliveryProvenance,
    BamfTrainingRow, BamfTrainingBatch, PaddedMicrobatch,
    _invalid, _freeze, require_current_release,
)
from .atlas_training_delivery import (
    pad_microbatches, attach_auxiliaries, execute_with_backend,
    capture_realized_delivery, require_independent_cohorts, resolve_batch_rules,
)


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


def compile_training_batch(delivered_rows, source_context: SourceExecutionContext,
                           topology, *, delivery: DeliveredTeaching, delivery_capability: str,
                           delivery_release_sha256: str, teacher_strategy: dict,
                           requested_count: int, optimizer_step_seed: int,
                           rehearsal_by_id: dict, visible_ends: dict,
                           source_ast_for: Callable, compile_prefix: Callable,
                           feature_requests_for: Callable, features_for: Callable, answer_plan_for: Callable,
                           frames_for_ast: Callable, task_scope: TaskScope,
                           source_frontier: SourceFrontier,
                           eligibility_policy: ContextPolicy, generation_binding: str,
                           target_encoders: dict | None = None, sealed_holdout_ids=()) -> BamfTrainingBatch:
    """Compile source-oracled delivery using explicit frozen A05/A06 seams."""
    if not isinstance(source_context, SourceExecutionContext):
        _invalid('SOURCE_CONTEXT_REQUIRED')
    if not isinstance(delivered_rows, (tuple, list)) or not delivered_rows:
        _invalid('DELIVERED_ROWS_REQUIRED')
    if any(not callable(fn) for fn in (source_ast_for, compile_prefix, feature_requests_for, features_for,
                                           frames_for_ast, answer_plan_for)):
        _invalid('UPSTREAM_INTERFACES_REQUIRED')
    if (type(task_scope) is not TaskScope
            or type(source_frontier) is not SourceFrontier
            or type(eligibility_policy) is not ContextPolicy):
        _invalid('CONTEXT_AUTHORITY_REQUIRED')
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
        frames = frames_for_ast(ast)
        if (type(frames) is not tuple or not frames
                or any(type(frame) is not ContextEligibility for frame in frames)):
            _invalid('CONTEXT_SOURCE_FRAMES_REQUIRED')
        eligible = _check_context_eligibility(
            frames, task_scope, source_frontier, eligibility_policy)
        if type(eligible) is not EligibleContext:
            _invalid('CONTEXT_NOT_ELIGIBLE')
        eligibility_digest = eligible.digest
        prefix = compile_prefix(ast, len(visible), release, topology)
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
