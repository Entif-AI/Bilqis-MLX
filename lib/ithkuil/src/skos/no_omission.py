"""Global stable-row no-omission gate for semantic coverage receipts (#69)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json

from .coverage_schema import STATUSES, validate_coverage_receipt
from .errors import ProfileError


@dataclass(frozen=True, order=True)
class SourceRowIdentity:
    domain: str
    table: str
    key: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.domain, self.table, self.key)):
            raise ProfileError("SOURCE_ROW_ID_INVALID", repr((self.domain, self.table, self.key)))

    @property
    def locator(self) -> str:
        return f"{self.domain}:{self.table}:{self.key}"


@dataclass(frozen=True)
class NoOmissionResult:
    source_rows: int
    accounted_rows: int
    dispositions: tuple[tuple[str, int], ...]
    domain_rows: tuple[tuple[str, int], ...]

    def as_dict(self) -> dict:
        return {
            "schema": "bilqis.skos.no-omission/v1",
            "source_rows": self.source_rows,
            "accounted_rows": self.accounted_rows,
            "dispositions": dict(self.dispositions),
            "domain_rows": dict(self.domain_rows),
            "complete": self.source_rows == self.accounted_rows,
        }


def _receipt_entries(receipt: dict) -> list[tuple[SourceRowIdentity, dict]]:
    domains = receipt.get("domains") if isinstance(receipt, dict) else None
    if not isinstance(domains, dict):
        raise ProfileError("NO_OMISSION_DOMAINS_REQUIRED")
    entries: list[tuple[SourceRowIdentity, dict]] = []
    for domain, body in sorted(domains.items()):
        if not isinstance(body, dict) or not isinstance(body.get("rows"), list):
            raise ProfileError("NO_OMISSION_ROWS_REQUIRED", str(domain))
        for index, entry in enumerate(body["rows"]):
            if not isinstance(entry, dict):
                raise ProfileError("NO_OMISSION_ROW_INVALID", str(domain), str(index))
            try:
                row_id = SourceRowIdentity(domain, entry["table"], entry["key"])
            except (KeyError, ProfileError) as error:
                if isinstance(error, ProfileError):
                    raise
                raise ProfileError("NO_OMISSION_ROW_ID_MISSING", str(domain), str(index), str(error))
            entries.append((row_id, entry))
    return entries


def validate_no_omission(
    expected_source_rows: tuple[SourceRowIdentity, ...] | list[SourceRowIdentity],
    receipt: dict,
    *,
    strong_subjects: tuple[str, ...] | list[str] | set[str] = (),
) -> NoOmissionResult:
    expected = tuple(expected_source_rows)
    expected_counts = Counter(expected)
    duplicate_source = sorted(row for row, count in expected_counts.items() if count != 1)
    if duplicate_source:
        raise ProfileError(
            "SOURCE_ROW_ID_DUPLICATE",
            *(f"duplicate={row.locator}" for row in duplicate_source),
        )

    raw_entries = _receipt_entries(receipt)
    observed = [row_id for row_id, _ in raw_entries]
    observed_counts = Counter(observed)
    missing = sorted(set(expected) - set(observed))
    extra = sorted(set(observed) - set(expected))
    duplicates = sorted(row for row, count in observed_counts.items() if count != 1)
    if missing or extra or duplicates:
        raise ProfileError(
            "NO_OMISSION_MISMATCH",
            *(f"missing={row.locator}" for row in missing),
            *(f"extra={row.locator}" for row in extra),
            *(f"duplicate={row.locator}" for row in duplicates),
        )

    validate_coverage_receipt(receipt)
    strong = set(strong_subjects)
    dispositions = Counter()
    domain_rows = Counter()
    for row_id, entry in raw_entries:
        status = entry["status"]
        if status not in STATUSES:
            raise ProfileError("NO_OMISSION_STATUS_INVALID", row_id.locator, str(status))
        dispositions[status] += 1
        domain_rows[row_id.domain] += 1
        reason = entry.get("reason_code")
        owner = entry.get("owner")
        semantic_iri = entry.get("semantic_iri")
        if status == "IR_ONLY" and (not reason or not owner):
            raise ProfileError("IR_ONLY_RATIONALE_REQUIRED", row_id.locator)
        if status != "EMITTED" and semantic_iri and semantic_iri in strong:
            raise ProfileError(
                "NONEMITTED_ROW_HAS_STRONG_ASSERTION",
                row_id.locator,
                f"status={status}",
                f"semantic_iri={semantic_iri}",
            )
    return NoOmissionResult(
        source_rows=len(expected),
        accounted_rows=len(observed),
        dispositions=tuple((status, dispositions[status]) for status in STATUSES),
        domain_rows=tuple(sorted(domain_rows.items())),
    )


def no_omission_json_bytes(result: NoOmissionResult) -> bytes:
    return (json.dumps(result.as_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
