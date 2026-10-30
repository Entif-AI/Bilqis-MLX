"""B07.3 copy-on-write motif allocation state, not a generation publisher.

The B13/C retained-generation transaction must commit this candidate together
with the exact tensors, AdamW moments and source frontier. No function here
promotes a checkpoint or treats a candidate as accepted neural state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .atlas_engram import (
    CandidateMotifView, MotifBudget, MotifFrameInput, MotifKey, MotifManifest,
    OBSERVED_USE_ARITY,
    _digest, candidate_motif_manifest, prepare_motifs,
)


SNAPSHOT_SCHEMA = "bilqis.motif-allocation-snapshot/v1"
CANDIDATE_SCHEMA = "bilqis.motif-allocation-candidate/v1"
ALIAS_SCHEMA = "bilqis.motif-source-alias-artifact/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _valid_counts(counts: object) -> bool:
    return (
        isinstance(counts, tuple)
        and all(isinstance(item, tuple) and len(item) == OBSERVED_USE_ARITY
                and isinstance(item[0], str) and _SHA.fullmatch(item[0])
                and type(item[1]) is int and item[1] > 0
                for item in counts)
        and counts == tuple(sorted(counts))
        and len({item[0] for item in counts}) == len(counts)
    )


@dataclass(frozen=True)
class MotifAliasArtifact:
    """An explicit source-attested alias proposal, never an implicit remap."""

    old_release: str
    old_key_digest: str
    new_release: str
    new_key_digest: str
    source_attestation_digest: str
    schema_version: str = ALIAS_SCHEMA

    def __post_init__(self) -> None:
        if (any(not isinstance(value, str) or not _SHA.fullmatch(value)
                for value in (
                    self.old_release, self.old_key_digest,
                    self.new_release, self.new_key_digest,
                    self.source_attestation_digest))
                or (self.old_release, self.old_key_digest)
                == (self.new_release, self.new_key_digest)
                or self.schema_version != ALIAS_SCHEMA):
            _invalid("BAMF_MOTIF_ALIAS_INVALID")

    @property
    def source_identity(self) -> tuple[str, str]:
        return self.old_release, self.old_key_digest


@dataclass(frozen=True)
class MotifAllocationSnapshot:
    """Frozen allocation/counter/alias contents for one retained generation."""

    manifest: MotifManifest
    observed_uses: tuple[tuple[str, int], ...] = ()
    pending_keys: tuple[MotifKey, ...] = ()
    aliases: tuple[MotifAliasArtifact, ...] = ()
    schema_version: str = SNAPSHOT_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.manifest) is not MotifManifest
                or not _valid_counts(self.observed_uses)
                or not isinstance(self.pending_keys, tuple)
                or any(type(key) is not MotifKey
                       or key.semantic_release != self.manifest.semantic_release
                       for key in self.pending_keys)
                or len({key.digest for key in self.pending_keys})
                != len(self.pending_keys)
                or any(self.manifest.lookup(key) is not None
                       for key in self.pending_keys)
                or self.pending_keys != tuple(sorted(
                    self.pending_keys, key=lambda key: (
                        key.kind != "STRUCTURAL",
                        -dict(self.observed_uses).get(key.digest, 0),
                        key.digest)))
                or not isinstance(self.aliases, tuple)
                or any(type(alias) is not MotifAliasArtifact
                       or alias.new_release != self.manifest.semantic_release
                       for alias in self.aliases)
                or self.aliases != tuple(sorted(
                    self.aliases, key=lambda alias: alias.source_identity))
                or len({alias.source_identity for alias in self.aliases})
                != len(self.aliases)
                or any(alias.new_key_digest not in {
                    slot.key.digest for slot in self.manifest.slots}
                    for alias in self.aliases)
                or self.schema_version != SNAPSHOT_SCHEMA):
            _invalid("BAMF_MOTIF_SNAPSHOT_INVALID")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class CandidateMotifSnapshot:
    """A proposed next allocation state, never an acceptance receipt."""

    parent_snapshot_digest: str
    view: CandidateMotifView
    proposed: MotifAllocationSnapshot
    schema_version: str = CANDIDATE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.parent_snapshot_digest, str)
                or not _SHA.fullmatch(self.parent_snapshot_digest)
                or type(self.view) is not CandidateMotifView
                or type(self.proposed) is not MotifAllocationSnapshot
                or self.schema_version != CANDIDATE_SCHEMA):
            _invalid("BAMF_MOTIF_TRANSACTION_INVALID")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


def prepare_candidate_motif_snapshot(
    frames: tuple[MotifFrameInput, ...],
    parent: MotifAllocationSnapshot,
    budget: MotifBudget,
    *,
    source_aliases: tuple[MotifAliasArtifact, ...] = (),
) -> CandidateMotifSnapshot:
    """Compute the next counters and slots without changing the parent."""
    if (type(parent) is not MotifAllocationSnapshot
            or not isinstance(source_aliases, tuple)
            or any(type(item) is not MotifAliasArtifact
                   for item in source_aliases)):
        _invalid("BAMF_MOTIF_TRANSACTION_INVALID")
    view = prepare_motifs(
        frames, parent.manifest, budget,
        prior_observed_uses=parent.observed_uses,
        prior_pending=parent.pending_keys)
    manifest = candidate_motif_manifest(parent.manifest, view)
    aliases = tuple(sorted(
        (*parent.aliases, *source_aliases),
        key=lambda alias: alias.source_identity,
    ))
    proposed = MotifAllocationSnapshot(
        manifest, view.plan.observed_uses, view.plan.pending, aliases)
    return CandidateMotifSnapshot(parent.digest, view, proposed)


def verify_candidate_motif_snapshot(
    candidate: CandidateMotifSnapshot,
    *,
    frames: tuple[MotifFrameInput, ...],
    parent: MotifAllocationSnapshot,
    budget: MotifBudget,
    source_aliases: tuple[MotifAliasArtifact, ...] = (),
) -> None:
    """Replay against exact parent and source inputs before B13 staging.

    A successful replay proves only deterministic candidate contents.
    The accepted-generation owner must separately validate source equivalence,
    neural tensors, optimizer custody and retained-learning acceptance.
    """
    if type(candidate) is not CandidateMotifSnapshot:
        _invalid("BAMF_MOTIF_TRANSACTION_INVALID")
    expected = prepare_candidate_motif_snapshot(
        frames, parent, budget, source_aliases=source_aliases)
    if candidate != expected:
        _invalid("BAMF_MOTIF_TRANSACTION_REPLAY_MISMATCH")
