"""Bind source/outcome salience labels to exact C02 delivery rows."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json

from ..learning.atlas_salience import SalienceEvidence, derive_salience, verify_salience_inputs
from ..learning.salience_contracts import AuthoritySnapshot, _invalid, _name, _sha, _signature, _signing_bytes
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from .atlas_training_adapter import BamfTrainingBatch, BamfTrainingRow, attach_auxiliaries, require_current_release


def _row_digest(row):
    # C02 feature records may contain finite scalar floats. Bind exact JSON values.
    try:
        payload = json.dumps((asdict(row.model_input), asdict(row.provenance)),
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError):
        _invalid("BAMF_SALIENCE_ROW_NOT_SERIALIZABLE")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class RowSalienceBinding:
    release_sha256: str
    generation_binding: str
    delivered_content_sha256: str
    row_id: str
    row_digest: str
    salience_inputs_digest: str
    source_owner: str
    signature_hex: str
    schema_version: str = "bilqis.c06.row-salience-binding/v1"

    def __post_init__(self):
        if (not all(_sha(value) for value in (self.release_sha256, self.generation_binding,
                self.delivered_content_sha256, self.row_digest, self.salience_inputs_digest))
                or not _name(self.row_id) or not _name(self.source_owner)
                or not _signature(self.signature_hex)
                or self.schema_version != "bilqis.c06.row-salience-binding/v1"):
            _invalid("BAMF_SALIENCE_ROW_BINDING_INVALID")

    @classmethod
    def for_row(cls, batch, row, evidence, *, source_owner, signature_hex):
        if (not isinstance(batch, BamfTrainingBatch) or not isinstance(row, BamfTrainingRow)
                or row not in batch.rows or not isinstance(evidence, SalienceEvidence)):
            _invalid("BAMF_SALIENCE_ROW_BINDING_INPUT_INVALID")
        return cls(batch.release_sha256, batch.generation_binding, batch.delivered_content_sha256,
                   row.provenance.row_id, _row_digest(row), evidence.basis.digest(), source_owner, signature_hex)

    def signing_bytes(self):
        return _signing_bytes(self)


def attach_salience_labels(batch, source_context, records, authority_snapshot, *, verify_existing):
    if (not isinstance(batch, BamfTrainingBatch) or not isinstance(records, tuple)
            or not isinstance(authority_snapshot, AuthoritySnapshot) or not callable(verify_existing)
            or any(not isinstance(record, tuple) or len(record) != 2
                   or not isinstance(record[0], RowSalienceBinding)
                   or not isinstance(record[1], SalienceEvidence) for record in records)
            or len({record[0].row_id for record in records}) != len(records)
            or len({row.provenance.row_id for row in batch.rows}) != len(batch.rows)):
        _invalid("BAMF_SALIENCE_ROW_LABEL_INPUT_INVALID")
    require_current_release(batch, source_context, generation_binding=batch.generation_binding)
    rows = {row.provenance.row_id: row for row in batch.rows}
    labels = {}
    for binding, evidence in records:
        row = rows.get(binding.row_id)
        basis = evidence.basis
        if (row is None or binding.release_sha256 != batch.release_sha256
                or binding.generation_binding != batch.generation_binding
                or binding.delivered_content_sha256 != batch.delivered_content_sha256
                or binding.row_digest != _row_digest(row)
                or binding.salience_inputs_digest != basis.digest()
                or basis.snapshot != authority_snapshot or basis.context not in authority_snapshot.contexts
                or evidence.scope != basis.context or basis.context.semantic_release != batch.release_sha256
                or basis.context.generation_digest != batch.generation_binding
                or row.provenance.capability_id != basis.context.capability_id
                or not row.provenance.source_family_id or not row.provenance.episode_id
                or row.provenance.source_family_id != basis.context.source_family_id):
            _invalid("BAMF_SALIENCE_ROW_OR_EVIDENCE_DRIFT")
        verified = verify_salience_inputs(basis.facts, basis.policy, authority_snapshot, basis.context)
        if derive_salience(verified) != evidence:
            _invalid("BAMF_SALIENCE_ROW_LABEL_EVIDENCE_DRIFT")
        authority_snapshot.registry.verify_detached(binding.source_owner,
            DependencyRef(DependencyKind.ARTIFACT, "salience-row:" + binding.row_id),
            binding.signature_hex, binding.signing_bytes())
        labels[binding.row_id] = {}
        for name in ('impact', 'exigency', 'novelty'):
            metric = getattr(evidence, name)
            if metric.supervised_label is not None:
                receipt = ('bilqis.c06.auxiliary-label/v1', binding.salience_inputs_digest,
                           binding.row_digest, binding.signature_hex, metric.rule_ids, metric.fact_ids)
                labels[binding.row_id][name] = (metric.supervised_label, metric.origin.value, receipt)
    merged = {}
    for row_id, row in rows.items():
        existing = {}
        for item in row.auxiliaries:
            if (not isinstance(item, tuple) or len(item) != 4 or item[0] in existing
                    or verify_existing(row_id, *item) is not True):
                _invalid("BAMF_SALIENCE_EXISTING_AUXILIARY_UNVERIFIED")
            existing[item[0]] = item[1:]
        for name, label in labels.get(row_id, {}).items():
            if name in existing and existing[name] != label:
                _invalid("BAMF_SALIENCE_AUXILIARY_CONFLICT")
            existing[name] = label
        merged[row_id] = existing
    # C02 replaces all head labels. Supply the verified complete map to preserve other heads.
    labelled = attach_auxiliaries(batch, merged, verify=lambda row_id, name, value, regime, receipt:
        merged.get(row_id, {}).get(name) == (value, regime, receipt))
    return replace(labelled, rows=tuple(
        changed if labels.get(original.provenance.row_id) else original
        for original, changed in zip(batch.rows, labelled.rows)))
