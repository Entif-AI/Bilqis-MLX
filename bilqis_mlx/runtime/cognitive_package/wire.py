"""Canonical UTF-8 JSON transport; payload bytes are lowercase hexadecimal."""
from dataclasses import asdict
import json
from .contracts import PackageArtifact, PackageBinding, PackageKind, SourceRights, invalid
from .records import CognitivePackage


def encode_package(package):
    raw = asdict(package)
    raw['artifacts'] = [dict(artifact_id=a.artifact_id, kind=a.kind.value,
                             payload=a.payload.hex()) for a in package.artifacts]
    return json.dumps(raw, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            invalid('duplicate wire key')
        result[key] = value
    return result


def decode_package(value):
    try:
        if type(value) is not str:
            invalid('invalid package wire type')
        value.encode('utf-8')
        raw = json.loads(value, object_pairs_hook=unique_object)
        raw['binding'] = PackageBinding(**raw['binding'])
        rights = raw['rights']
        for key in ('public_artifact_digests', 'revoked_artifact_digests', 'revocation_lineage'):
            if type(rights[key]) is not list:
                invalid('invalid wire clearance list')
            rights[key] = tuple(rights[key])
        raw['rights'] = SourceRights(**rights)
        raw['artifacts'] = tuple(PackageArtifact(**{
            **a, 'kind': PackageKind(a['kind']), 'payload': bytes.fromhex(a['payload'])
        }) for a in raw['artifacts'])
        package = CognitivePackage(**raw)
        if package.canonical_json != value:
            invalid('noncanonical package wire')
        return package
    except (KeyError, TypeError, ValueError, RecursionError):
        invalid('invalid package wire record')
