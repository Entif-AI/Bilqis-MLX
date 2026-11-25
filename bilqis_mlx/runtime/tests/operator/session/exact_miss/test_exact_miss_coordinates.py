"""Actual ordinary source compilation and retained transaction coordinates."""
from types import SimpleNamespace as N

import pytest

from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning._atlas_candidate import step as optimizer_step
from bilqis_mlx.runtime import factory_retention_owner as retention
from bilqis_mlx.runtime.candidate import execution
from bilqis_mlx.runtime.learning_first_compiler import (
    compile_learning_first_training_batch,
)
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts import rehearsal
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.factory_training_preparation import (
    prepare_learning_first_source_inputs_ahead,
)
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance
from bilqis_mlx.runtime.tests.capability.factory.retention.test_exact_miss_reissue import (
    _prepare, _plan, _deliver, visit_fixture,
)
from bilqis_mlx.runtime.tests.correction.capability_support_owner_support import source_qualified_state
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import HP
from bilqis_mlx.runtime.tests.operator.pre_neural import (
    test_learning_first_source_path as source_path_tests,
)
from bilqis_mlx.runtime.tests.operator.pre_neural.pre_neural_journey_support import (
    historical_school_release, journey_source, portable_atlas_snapshot, wide_shape_patch,
)


@pytest.fixture
def source_fixture():
    fixture = source_path_tests.LearningFirstSourcePathTests()
    fixture.setUp()
    try:
        yield fixture
    finally:
        fixture.tearDown()


def test_actual_compiled_replay_survives_transaction_source_exclusions(
        source_fixture, monkeypatch, tmp_path):
    fixture = source_fixture
    fixture.current, fixture.parent_graph = historical_school_release()
    snapshot = portable_atlas_snapshot()
    schema, features, selection = journey_source(snapshot)
    with wide_shape_patch(len(snapshot.abi_entries)):
        fixture.publish_matching_genesis(snapshot, schema, features)
        with fixture.journey_mounts(snapshot, schema, features, selection), evidence_mode(strict=False):
            parent, context, _atlas, _feature = _execution_context(fixture.run)
            authenticated = context._accepted_feature_context
            f = visit_fixture(context, monkeypatch, tmp_path, 'A.IDENTITY')
            prospective = _prepare(f)
            plan = _plan(f, prospective)
            replay = rehearsal.materialize_rehearsal_rows(
                context, plan, 1, reserved_rows=f.direct)
            observation = _deliver(f, plan, replay)
            rows = (*f.direct, *replay.prior, *replay.preservation, *replay.retention_support)
            object.__setattr__(context, '_accepted_feature_context', authenticated)
            prepared = prepare_learning_first_source_inputs_ahead(
                context, authenticated, rows, source_seed=f.selection.offer.source_seed,
                source_each=len(f.direct))
            batch = compile_learning_first_training_batch(
                rows, context, parent.topology, delivery_capability='A.IDENTITY',
                teacher_strategy=f.selection.policy, requested_count=len(rows),
                optimizer_step_seed=7, visit_provenance=visit_provenance('A.IDENTITY'),
                rehearsal_by_id=replay.by_id, fresh_support_by_id={},
                generation_binding=f.cache.generation_binding,
                prepared_model_sources=prepared.model_sources,
                delivered_content_sha256=content_digest(rows))
    # Numerical fixture boundary: supply an independently advanced tiny
    # disposable optimizer from the existing custody witness. The ordinary
    # admission owner and real transaction issuance consume compiled metadata.
    tiny, _, updated, _ = source_qualified_state()
    monkeypatch.setattr(execution, 'derive_participation_inputs', lambda _: (None, None))
    monkeypatch.setattr(optimizer_step, '_learning_first_optimizer_inputs',
                        lambda *_: (None, None, None))
    monkeypatch.setattr(optimizer_step, '_adamw_update', lambda *a, **kw: updated.optimizer)
    transaction = execution._learning_first_admit(
        N(retained_state=tiny, topology=None, extents=None),
        f.cache, None, N(execution=object(), gradients={}), HP, 1.0,
        N(training_batch=batch))
    metadata = tuple(row.provenance for row in batch.rows)
    expected = tuple(sorted({('A.IDENTITY', row.source_family_id, row.episode_id)
                             for row in metadata}))
    assert transaction.training_source_coordinates == expected
    families, episodes = retention._training_exclusions(transaction)
    for row, grant in plan.exact_miss_instruction.pairs:
        if row['id'] in observation.controls['exact_miss_delivery_ids']:
            assert grant.source_family_id in families
            assert set(grant.episode_ids) <= set(episodes)
            assert row['id'] in {item.row_id for item in metadata}
    assert len(observation.controls['exact_miss_delivery_ids']) == 3
    assert transaction.update_steps == 1
    assert resolve_candidate(transaction, accepted=False) is tiny
    assert resolve_candidate(transaction, accepted=True).optimizer is updated.optimizer
