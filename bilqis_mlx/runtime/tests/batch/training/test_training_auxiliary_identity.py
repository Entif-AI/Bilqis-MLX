"""C02 label identity remains separate from provenance identity."""
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_training_authority import _issue, extend_training_dependencies
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfDeliveryProvenance, BamfTrainingRow, _canonical_digest,
    _issue_training_batch, _reissue_training_batch,
)
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef


@pytest.fixture
def issued_batch():
    dep = DependencyRef(DependencyKind.SOURCE, 'source:one')
    provenance = BamfDeliveryProvenance(
        'row-1', 'a' * 64, 'source-1', 'cap-1', None, (), 1, 1, None, 1,
        visit_provenance('cap-1'), 'family-1', 'episode-1', (dep,))
    row = BamfTrainingRow(None, None, None, provenance)
    batch = _issue_training_batch('b' * 64, 'c' * 64, 'd' * 64, 'cap-1', (row,))
    return batch, SimpleNamespace(source_row={'id': 'row-1'})


def issue(batch, source):
    row = batch.rows[0]
    return _issue(batch, source, row.provenance, row.auxiliaries)


def test_labels_bind_exact_values_and_receipts_without_changing_batch_identity(issued_batch):
    batch, source = issued_batch
    variants = (
        (('impact', 1, 'SOURCE', 'receipt-1'),),
        (('novelty', 1, 'SOURCE', 'receipt-1'),),
        (('impact', 2, 'SOURCE', 'receipt-1'),),
        (('impact', 1, 'OUTCOME', 'receipt-1'),),
        (('impact', 1, 'SOURCE', 'receipt-2'),),
    )
    identities = []
    for labels in variants:
        labelled = _reissue_training_batch(batch, rows=(replace(batch.rows[0], auxiliaries=labels),))
        assert labelled.authority_digest == batch.authority_digest
        authority = issue(labelled, source)
        assert authority.auxiliary_labels_sha256 == _canonical_digest(labels)
        identities.append(authority.digest)
    assert len(set(identities)) == len(variants)


def test_absent_labels_preserve_old_digest_and_extension_retains_binding(issued_batch):
    batch, source = issued_batch
    plain = issue(batch, source)
    assert plain.auxiliary_labels_sha256 is None
    old_payload = {
        'release': plain.release_sha256, 'generation': plain.generation_binding,
        'batch': plain.training_batch_sha256, 'capability': plain.delivery_capability,
        'row': plain.source_row_id, 'row_sha256': plain.source_row_sha256,
        'source_family': plain.source_family_id, 'episode': plain.episode_id,
        'visit_id': plain.visit_id,
        'immediate_dependencies': tuple((ref.kind.value, ref.key) for ref in plain.immediate_dependencies),
    }
    wire = json.dumps(old_payload, sort_keys=True, separators=(',', ':'))
    assert plain.digest == hashlib.sha256(wire.encode()).hexdigest()
    labels = (('impact', 0, 'SOURCE', 'receipt'),)
    labelled = _reissue_training_batch(batch, rows=(replace(batch.rows[0], auxiliaries=labels),))
    authority = issue(labelled, source)
    extended = extend_training_dependencies(authority, (DependencyRef(DependencyKind.SOURCE, 'source:two'),))
    assert extended.auxiliary_labels_sha256 == authority.auxiliary_labels_sha256
    assert extended.digest != authority.digest
    object.__setattr__(extended, 'auxiliary_labels_sha256', 'invalid')
    with pytest.raises(BilqisError):
        extended.__post_init__()
