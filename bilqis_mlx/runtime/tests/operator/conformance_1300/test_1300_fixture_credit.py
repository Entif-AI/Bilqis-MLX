"""Cheap contracts for disposable #1300 fixture evidence credit."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.factory.autonomy import EvidenceReceipt
from bilqis_mlx.runtime.tests.operator.conformance_1300_support.runtime import (
    _record_fixture_evidence_once,
)


CHECKPOINT = "a" * 64
COHORT = "b" * 64


def _receipt(*, obligation_id="A.IDENTITY/direct", evidence_id="fixture-id"):
    return EvidenceReceipt(
        obligation_id,
        evidence_id,
        CHECKPOINT,
        2,
        COHORT,
        12,
        True,
    )


def test_fixture_evidence_credit_reuses_exact_existing_receipt():
    receipt = _receipt()
    ledger = SimpleNamespace(receipts=(receipt,))

    with patch(
        "bilqis_mlx.runtime.tests.operator.conformance_1300_support.runtime.record_evidence"
    ) as record:
        result = _record_fixture_evidence_once(
            object(), ledger, receipt,
            plan=object(), checkpoint=CHECKPOINT, step=2,
        )

    assert result is ledger
    record.assert_not_called()


def test_fixture_evidence_credit_rejects_same_id_with_different_payload():
    ledger = SimpleNamespace(receipts=(_receipt(),))
    conflicting = _receipt(obligation_id="D.EVENT_OCCURRENCE/direct")

    with pytest.raises(
        ValueError, match="CONFORMANCE_1300_FIXTURE_EVIDENCE_ID_COLLISION"
    ):
        _record_fixture_evidence_once(
            object(), ledger, conflicting,
            plan=object(), checkpoint=CHECKPOINT, step=2,
        )
