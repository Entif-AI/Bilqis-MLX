"""Deterministic, research-only projection from historical number IDs to NI forms."""
from __future__ import annotations

from dataclasses import asdict
import json

from .ni_construction import (
    Numeral, generate_numeral, parse_numeral, NUMBER_SOURCE, REVIEW_VERSION,
)

SCHEMA = "bilqis.mlx.ni-constructibility/1"
EVIDENCE_VERSION = "ni-construction/20261015-a"

# Literal spellings as published in the official grammar, Chapter 13.4.
OFFICIAL_WITNESSES = {
    21: ("wallärsa", "THM", True),
    26: ("cpalärsa", "THM", False),
    42: ("ksalirsa", "THM", False),
    72: ("ksalorsa", "THM", False),
    100: ("gzalui", "PAR", False),
}


def rows() -> list[dict]:
    result = []
    for value in range(101):
        citation = OFFICIAL_WITNESSES.get(value)
        case = citation[1] if citation else "THM"
        shortcut = citation[2] if citation else False
        constructed = generate_numeral(Numeral(value, case, shortcut))
        decoded = parse_numeral(constructed.surface)
        if (decoded.semantics["value"] != value
                or decoded.semantics["case"] != case
                or decoded.semantics["shortcut"] != shortcut):
            raise ValueError("NI_CONSTRUCTION_ROUNDTRIP_MISMATCH")
        if citation and constructed.surface != citation[0]:
            raise ValueError("NI_EXTERNAL_EXAMPLE_MISMATCH")
        result.append({
            "historical_token_id": value + 121,
            "historical_token": "school.number." + str(value),
            "historical_semantics": "exact integer " + str(value),
            "ni_surface": constructed.surface,
            "ni_case": case,
            "shortcut": shortcut,
            "ni_stem": 1,
            "ni_specification": "BSC",
            "ni_semantics": "set/cardinality",
            "attestation": "LITERAL_OFFICIAL_EXAMPLE" if citation
                else "RULE_DERIVED_NOT_INDEPENDENTLY_ATTESTED",
            "source": NUMBER_SOURCE,
            "source_locus": "§13.4" if citation else "§13.2, §13.4 (rules)",
            "conformance": "BOUNDED_SUBSET_ONLY_NO_GENERAL_NI_CERTIFICATION",
            "token_learned": False,
            "model_changed": False,
            "neural_updates": 0,
        })
    return result


def census() -> dict:
    entries = rows()
    return {
        "schema": SCHEMA,
        "version": EVIDENCE_VERSION,
        "review_version": REVIEW_VERSION,
        "source": NUMBER_SOURCE,
        "entries": entries,
        "matched_official_examples": sum(
            item["attestation"] == "LITERAL_OFFICIAL_EXAMPLE"
            for item in entries
        ),
        "grammar_derived_pending_independent_attestation": sum(
            item["attestation"] == "RULE_DERIVED_NOT_INDEPENDENTLY_ATTESTED"
            for item in entries
        ),
        "neural_updates": 0,
        "model_abi_unchanged": True,
    }


def main() -> None:
    print(json.dumps(census(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
