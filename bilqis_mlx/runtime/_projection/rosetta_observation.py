"""Native Rosetta Observation consumption through an explicitly pinned local tool."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .bamf_projection import BamfProjectionEvent, ProjectionDomainContract, _invalid, _sha


@dataclass(frozen=True)
class RosettaRuntime:
    node_executable: str
    bridge_path: Path
    bridge_sha256: str
    owner_revision: str

    def __post_init__(self):
        if (not isinstance(self.node_executable, str) or not self.node_executable
                or not isinstance(self.bridge_path, Path) or not _sha(self.bridge_sha256)
                or not isinstance(self.owner_revision, str)
                or re.fullmatch('[0-9a-f]{40}', self.owner_revision) is None):
            _invalid('BAMF_C10_ROSETTA_RUNTIME_INVALID')


@dataclass(frozen=True)
class RosettaObservation:
    tile_json: str
    bridge_sha256: str
    owner_revision: str
    visibility: str = 'INTERNAL_ONLY'

    @property
    def tile(self):
        return json.loads(self.tile_json)


def project_rosetta_observation(event, runtime, *, created_at):
    if not isinstance(event, BamfProjectionEvent) or not isinstance(runtime, RosettaRuntime):
        _invalid('BAMF_C10_ROSETTA_INPUT_INVALID')
    if (not isinstance(created_at, str)
            or re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', created_at) is None):
        _invalid('BAMF_C10_ROSETTA_TIMESTAMP_INVALID')
    try:
        datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    except ValueError:
        _invalid('BAMF_C10_ROSETTA_TIMESTAMP_INVALID')
    if any(value > 2**53 - 1 for value in (event.as_of, event.event.source_time,
            event.event.effective_time, event.event.observed_at, event.event.recorded_at)):
        _invalid('BAMF_C10_ROSETTA_UNSAFE_INTEGER')
    path = runtime.bridge_path
    if (path.is_symlink() or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != runtime.bridge_sha256):
        _invalid('BAMF_C10_ROSETTA_BRIDGE_DRIFT')
    domain = ProjectionDomainContract(Path('/unused'), event.source_id, event.release_digest,
        event.model_digest, event.evaluator_digest, event.rights_digest, event.as_of)
    raw = json.loads(event.event.payload_json)
    source_xid = raw.get('native_event_id', raw.get('owner_source_event_id', raw.get('correction_event_id')))
    if (source_xid is not None and (not isinstance(source_xid, str) or not source_xid)
            or raw.get('verification_mode') not in (None, 'DISPOSABLE_CONTRACT')):
        _invalid('BAMF_C10_ROSETTA_SOURCE_REFERENCE_INVALID')
    signal = json.dumps({'schema': 'bilqis.c10.rosetta-observation-signal/v1',
        'akasha_event_id': event.event.event_id, 'source_event_xid': source_xid,
        'receipt_sha256': event.event.source_receipt_sha256, 'payload_sha256': event.event.payload_digest,
        'domain_digest': domain.digest, 'event_kind': event.event.kind.value,
        'fixture_mode': raw.get('verification_mode'),
        'source_time': event.event.source_time, 'effective_time': event.event.effective_time,
        'observed_at': event.event.observed_at, 'recorded_at': event.event.recorded_at},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    payload = {'observationId': 'bilqis.bamf.c10:observation:' + domain.digest + ':' + event.event.event_id,
               'source': 'sha256:' + event.event.source_receipt_sha256, 'signal': signal}
    request = {'schema': 'bilqis.c10.rosetta-observation-request/v1',
               'owner_revision': runtime.owner_revision, 'createdAt': created_at, **payload}
    try:
        result = subprocess.run([runtime.node_executable, str(path)],
            input=json.dumps(request, ensure_ascii=False, allow_nan=False), text=True,
            encoding='utf-8', capture_output=True, timeout=10, check=True)
        response = json.loads(result.stdout)
        tile = response['tile']
        if (set(response) != {'schema', 'owner_revision', 'verified', 'tile'}
                or response['schema'] != 'bilqis.c10.rosetta-observation-response/v1'
                or response['owner_revision'] != runtime.owner_revision or response['verified'] is not True
                or set(tile) != {'cid', 'kind', 'pack', 'version', 'parents', 'createdAt', 'canonical', 'payload'}
                or tile['kind'] != 'rosetta.observation' or tile['pack'] != 'bilqis.bamf.c10'
                or tile['version'] != '0.1.0' or tile['parents'] != []
                or tile['createdAt'] != created_at or tile['payload'] != payload
                or not isinstance(tile['canonical'], str) or not tile['canonical']
                or not isinstance(tile['cid'], str)
                or re.fullmatch('cidv1-sha256-[0-9a-f]{64}', tile['cid']) is None):
            _invalid('BAMF_C10_ROSETTA_RESPONSE_DRIFT')
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        _invalid('BAMF_C10_ROSETTA_OWNER_REJECTED')
    return RosettaObservation(json.dumps(tile, sort_keys=True, separators=(',', ':'), ensure_ascii=False),
                              runtime.bridge_sha256, runtime.owner_revision)
