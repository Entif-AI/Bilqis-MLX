"""Portable checks at the source/host supervision boundary."""
from types import SimpleNamespace

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.salience_training import SalienceLabelRequest, prepare_salience_training
from bilqis_mlx.runtime.tests.model import test_salience_auxiliaries as support


@pytest.fixture
def signed():
    fixture = support.SalienceAuxiliaryTests()
    fixture.setUp()
    yield fixture
    fixture.fixture.doCleanups()


def test_request_rejects_invalid_inputs(signed):
    record = (signed.binding(), signed.evidence)
    with pytest.raises(BilqisError):
        SalienceLabelRequest([record], signed.snapshot, lambda *args: False)
    with pytest.raises(BilqisError):
        SalienceLabelRequest((record,), signed.snapshot, None)
    with pytest.raises(BilqisError):
        SalienceLabelRequest((record, record), signed.snapshot, lambda *args: False)


def test_preparation_requires_real_accepted_host(signed):
    request = SalienceLabelRequest(((signed.binding(), signed.evidence),), signed.snapshot,
                                   lambda *args: False)
    prepared = SimpleNamespace(training_batch=signed.batch)
    with pytest.raises(BilqisError) as error:
        prepare_salience_training(prepared, signed.fixture.context, request)
    assert error.value.context['reason'] == 'FACTORY_SOURCE_CORRECTION_RUNTIME_REQUIRED'


def test_current_generation_and_registry_are_checked(signed):
    # Isolate the comparison only; this is not evidence of accepted host custody.
    from bilqis_mlx.runtime import salience_training
    request = SalienceLabelRequest(((signed.binding(), signed.evidence),), signed.snapshot,
                                   lambda *args: False)
    cache = SimpleNamespace(generation_binding=signed.batch.generation_binding)
    salience_training._require_current_identity(cache, signed.snapshot.registry, request, signed.batch)
    cache.generation_binding = 'f' * 64
    with pytest.raises(BilqisError):
        salience_training._require_current_identity(cache, signed.snapshot.registry, request, signed.batch)
    cache.generation_binding = signed.batch.generation_binding
    with pytest.raises(BilqisError):
        salience_training._require_current_identity(cache, SimpleNamespace(digest='f' * 64), request, signed.batch)


def test_consumption_uses_rederived_row_and_rejects_auxiliary_identity_drift(signed, monkeypatch):
    # Boundary unit test uses stand-ins; accepted-host and B11 integration need Studio.
    from bilqis_mlx.runtime import salience_training
    from bilqis_mlx.runtime import accepted_corrections
    from bilqis_mlx.runtime.atlas_training_authority import _issue
    request = SalienceLabelRequest(((signed.binding(), signed.evidence),), signed.snapshot,
                                   lambda *args: False)
    batch = signed.batch
    labelled = salience_training._attach(batch, signed.fixture.context, request)
    row = labelled.rows[0]
    source = SimpleNamespace(source_row=signed.fixture.context.draw_rows(
        seed=17, capability='Z.C0', each=2)[0])
    authority = _issue(labelled, source, row.provenance, row.auxiliaries)
    no_op = SimpleNamespace(require=lambda *args: None)
    packed_owner = SimpleNamespace(require_row=lambda *args: None)
    encoded = SimpleNamespace(compiled=SimpleNamespace(rows=(row.model_input.prefix,)),
                              features=object(), packed_frame_artifact_owner=packed_owner)
    compiled = SimpleNamespace(training_authority=authority, sources=(source,),
                               compiled=encoded, atlas_feature_artifact_owner=no_op)
    owner = SimpleNamespace(require=lambda: None)
    supervision = object.__new__(salience_training.SalienceSupervision)
    for name, value in (('_batch', batch), ('_request', request),
                        ('_source_context', signed.fixture.context), ('_owner', owner),
                        ('_compiled_rows', (compiled,))):
        object.__setattr__(supervision, name, value)
    monkeypatch.setattr(salience_training, '_current', lambda *args: SimpleNamespace(
        generation_binding=batch.generation_binding, accepted_manifest_sha256='a' * 64))
    monkeypatch.setattr(type(signed.fixture.context), 'register_compiled_batch', lambda *args: None)
    monkeypatch.setattr(accepted_corrections, 'register_accepted_target', lambda *args: None)
    assert supervision.labels_for(compiled) == {'impact': 2, 'exigency': 1}
    object.__setattr__(authority, 'auxiliary_labels_sha256', 'f' * 64)
    with pytest.raises(BilqisError) as error:
        supervision.labels_for(compiled)
    assert error.value.context['reason'] == 'BAMF_SALIENCE_COMPILED_ROW_MISMATCH'
