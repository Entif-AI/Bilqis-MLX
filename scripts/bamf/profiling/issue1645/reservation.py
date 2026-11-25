"""Research-only cohort reservation and exposure audit; never issues an exam."""
from collections import Counter
from hashlib import sha256
import argparse
import json
from pathlib import Path


CAPABILITIES = ("A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS")
GOLD = ("TRUE", "FALSE")
BINDINGS = (
    "manifest_sha256", "release_sha256", "semantic_graph_sha256",
    "rubric_sha256", "generator_version",
)
ROWS_PER_GOLD = 6


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def semantic_key(row):
    return digest([row["capability"], row["tokens"], row["answer_kind"]])


def witness_key(row, gold):
    # Match recorded delivery receipts, including their whitespace encoding.
    value = [row["capability"], row["tokens"], gold, row["answer_kind"]]
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def prepare(prepared):
    """Freeze both labels of every reserved input, before any new exposure.

    This is a reservation candidate, not approval or proof of past independence.
    The caller still needs source-owner approval and an enforcing source boundary.
    """
    cohort = prepared["prospective"]
    require(cohort["status"] ==
            "PREPARED_NOT_ISSUED_NOT_INDEPENDENT_UNTIL_EXCLUSION_ENFORCED",
            "unexpected preparation status")
    rows = cohort["rows"]
    require(digest(rows) == cohort["sha256"], "cohort digest mismatch")
    require(cohort["count"] == len(rows), "cohort count mismatch")
    bindings = {field: prepared[field] for field in BINDINGS}
    require(all(bindings.values()), "missing provenance")
    counts, reserved, witnesses = Counter(), set(), set()
    for entry in rows:
        row = entry["row"]
        capability, gold = row["capability"], row["gold"]
        require(capability in CAPABILITIES and gold in GOLD, "outside source scope")
        key = semantic_key(row)
        require(entry["semantic_key"] == key, "semantic key mismatch")
        require(entry["row_key"] == witness_key(row, gold), "witness key mismatch")
        require(key not in reserved, "duplicate or conflicting input")
        reserved.add(key)
        witnesses.update(witness_key(row, label) for label in GOLD)
        counts[capability, gold] += 1
    require(all(counts[cap, label] == ROWS_PER_GOLD
                for cap in CAPABILITIES for label in GOLD),
            "incomplete or unbalanced cohort")
    payload = {
        "schema": "bamf.research_reservation.v1",
        "status": "PREPARED_NOT_APPROVED_NOT_ISSUED",
        "bindings": bindings,
        "cohort_sha256": cohort["sha256"],
        "semantic_keys": sorted(reserved),
        "excluded_witness_keys": sorted(witnesses),
        "coverage": {cap: {label: counts[cap, label] for label in GOLD}
                     for cap in CAPABILITIES},
    }
    return {**payload, "reservation_sha256": digest(payload)}


def verify_reservation(reservation):
    payload = {key: value for key, value in reservation.items()
               if key != "reservation_sha256"}
    require(digest(payload) == reservation["reservation_sha256"],
            "reservation digest mismatch")
    require(payload["schema"] == "bamf.research_reservation.v1", "wrong schema")
    return payload


def require_allowed(reservation, rows, bindings):
    """Guard for an explicitly reserved disposable arm, before row delivery."""
    payload = verify_reservation(reservation)
    require(bindings == payload["bindings"], "source/manifest binding mismatch")
    denied = set(payload["semantic_keys"])
    require(not any(semantic_key(row) in denied for row in rows),
            "reserved assessment input in rehearsal delivery")


def audit(reservation, deliveries, bindings):
    """Retrospective receipt audit, never proof of complete exposure coverage."""
    payload = verify_reservation(reservation)
    require(bindings == payload["bindings"], "source/manifest binding mismatch")
    denied = set(payload["excluded_witness_keys"])
    overlaps, count = set(), 0
    for delivery in deliveries:
        keys = delivery["row_keys"]
        count += len(keys)
        overlaps.update(denied.intersection(keys))
    return {
        "reservation_sha256": reservation["reservation_sha256"],
        "recorded_delivery_rows": count,
        "overlap_witness_keys": len(overlaps),
        "status": "OVERLAP" if overlaps else "NO_OVERLAP_IN_SUPPLIED_RECEIPTS",
        "independence_certified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(json.loads(args.prepared.read_text())), indent=2))


if __name__ == "__main__":
    main()
