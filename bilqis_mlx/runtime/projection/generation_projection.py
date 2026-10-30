"""Post-commit projection adapter over the native immutable generation outbox."""
from dataclasses import dataclass
from pathlib import Path

from ...state_dag import read_generation
from ..checkpoints import _outbox_source_generation, _expected_outbox_events
from ..state import _fingerprint
from .akasha_outbox import AkashaEvent, NATIVE_EVENT_KINDS
from .bamf_projection import BamfProjectionEvent, project_generation_outbox, _invalid



@dataclass(frozen=True)
class GenerationProjection:
    run_id: str
    generation: int
    generation_digest: str
    projected_native_event_ids: tuple[str, ...]
    uncovered_native_event_ids: tuple[str, ...]
    receipt: object
    schema_version: str = 'bilqis.c10.generation-projection/v1'


def project_accepted_generation(run_dir: Path, generation: int, domain, *, graph):
    """Read accepted immutable history; no transient event dict can enter here.

    No checkpoint, teacher, journal or optimizer is written. Source-owned event
    times must be explicit; legacy events without them remain delivery debt.
    Unsupported native categories also remain explicit delivery debt.
    """
    record = read_generation(run_dir, generation)
    from ..admission import _require_executable_factory_admission
    release = _require_executable_factory_admission(run_dir, record, graph)
    if (release.release_sha256 != domain.release_digest
            or record.get('school', {}).get('current_student', {}).get('sha256') != domain.model_digest):
        _invalid('BAMF_C10_NATIVE_GENERATION_DOMAIN_DRIFT')
    outbox = record.get('delivery_outbox')
    if not isinstance(outbox, list) or not outbox:
        _invalid('BAMF_C10_NATIVE_GENERATION_OUTBOX_REQUIRED')
    source_generation, inherited = _outbox_source_generation(run_dir, record, outbox)
    _expected_outbox_events(record, outbox, source_generation)
    if inherited is not None:
        _invalid('BAMF_C10_INHERITED_OUTBOX_OWNER_REQUIRED')
    generation_digest = _fingerprint(record)
    projected, covered, uncovered = [], [], []
    for native in outbox:
        kind = NATIVE_EVENT_KINDS.get(native.get('event'))
        times = {key: native.get(key) for key in (
            "source_time", "effective_time", "observed_at", "recorded_at")}
        if kind is None or any(type(value) is not int or value < 0 for value in times.values()):
            uncovered.append(native['event_id'])
            continue
        payload = {'native_event_id': native['event_id'], 'native_event_digest': _fingerprint(native),
                   'run_id': record['run_id'], 'generation': generation,
                   'native_event_type': native['event']}
        event = AkashaEvent.from_payload(kind=kind,
            subject_id=record['run_id'] + ':' + native['event_id'],
            source_receipt_sha256=generation_digest, payload=payload,
            **times)
        projected.append(BamfProjectionEvent(event, domain.source_id, domain.release_digest,
            domain.model_digest, domain.evaluator_digest, domain.rights_digest, domain.as_of))
        covered.append(native['event_id'])
    receipt = project_generation_outbox(tuple(projected), domain)
    return GenerationProjection(record['run_id'], generation, generation_digest,
        tuple(covered), tuple(uncovered), receipt)
