"""Provisional lease contracts use isolated state and explicitly disposable authority."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionLease, AtlasSourceApproval, LeaseRunIdentity, ResourceCeiling,
    issue_atlas_lease, persist_atlas_lease, read_atlas_lease,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry, SourceAuthorityScope
from bilqis_mlx.learning.tests.test_atlas_salience import _REGISTRY, _signed
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

_REGISTRY = SourceAuthorityRegistry((replace(_REGISTRY.keys[0], allowed_scopes=tuple(sorted(
    (*_REGISTRY.keys[0].allowed_scopes, SourceAuthorityScope(DependencyKind.ARTIFACT, 'atlas-approval:')),
    key=lambda scope: (scope.kind.value, scope.key_prefix)))),))


def _run():
    return LeaseRunIdentity('fixture-lineage', '1' * 64, ModelTopologySpecV2().digest,
                            Checkpoint('2' * 64, 'bundles/disposable-origin', 0, True))


def _scope():
    return _signed(AtlasSourceApproval('fixture-approved-atlas', 'a' * 64,
        ('family:one',), ('operator:one',), 'b' * 64, 1, 'c' * 64, 'd' * 64,
        'e' * 64, True, True, 'fixture:salience-owner', '0' * 128))


def _lease():
    return issue_atlas_lease('fixture-lease', _run(), _scope(),
        ResourceCeiling(2, 2, 16384, 48 * 1024**3, 20 * 1024**3),
        requested_at=100, human_command_sha256='f' * 64, human_started=True,
        registry=_REGISTRY)
