"""B07.1 package acceptance surface over the split engram test owners.

Issue #456 names this module as the package-local acceptance entrypoint.  The
implementation tests are split beside their production owners under
``learning/_engram/tests``; this module keeps the stable contract path and the
legacy helper imports used by adjacent package tests without duplicating those
test bodies.
"""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import (
    INITIAL_MOTIF_CAPACITY,
    MOTIF_PAGE_STATE_BYTES,
    MotifBudget,
    MotifManifest,
    MotifSlot,
    motif_keys,
)
from bilqis_mlx.learning.atlas_engram_transaction import (
    CandidateMotifSnapshot,
    MotifAliasArtifact,
    MotifAllocationSnapshot,
    _prepare_candidate_motif_snapshot as prepare_candidate_motif_snapshot,
    _verify_candidate_motif_snapshot as verify_candidate_motif_snapshot,
)
from bilqis_mlx.learning._engram.tests.motif_fixtures import (
    RELEASE,
    full_first_page,
    source,
)
from bilqis_mlx.learning._engram.tests.test_atlas_engram_keys import (
    MotifKeyTests as _MotifKeyTests,
)
from bilqis_mlx.learning._engram.tests.test_atlas_engram_preparation import (
    MotifPreparationTests as _MotifPreparationTests,
)
from bilqis_mlx.learning._engram.tests.test_atlas_engram_transaction import (
    MotifTransactionTests as _MotifTransactionTests,
)


class MotifKeyAcceptanceTests(_MotifKeyTests):
    """Expose the split key proofs through the #456 contract module."""


class MotifPreparationAcceptanceTests(_MotifPreparationTests):
    """Expose the split preparation proofs through the #456 contract module."""


class MotifTransactionAcceptanceTests(_MotifTransactionTests):
    """Expose the split transaction proofs through the #456 contract module."""


__all__ = [
    "BilqisError",
    "CandidateMotifSnapshot",
    "INITIAL_MOTIF_CAPACITY",
    "MOTIF_PAGE_STATE_BYTES",
    "MotifAliasArtifact",
    "MotifAllocationSnapshot",
    "MotifBudget",
    "MotifManifest",
    "MotifSlot",
    "RELEASE",
    "TestCase",
    "full_first_page",
    "motif_keys",
    "prepare_candidate_motif_snapshot",
    "replace",
    "source",
    "verify_candidate_motif_snapshot",
    "MotifKeyAcceptanceTests",
    "MotifPreparationAcceptanceTests",
    "MotifTransactionAcceptanceTests",
]
