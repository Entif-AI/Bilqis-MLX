#!/usr/bin/env python3
"""Build disclosure-safe linguistic enrichment from the live Curriculum Registry cache.

The connector snapshots in _work/ are authenticated inputs and stay ignored.
Tracked outputs exclude pedagogical ordering, mastery/champion state, private
approval URLs, and proposed training schedules.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "_work" / "curriculum"
DATA = ROOT / "data"
SOURCES = ROOT / "sources"
WORKBOOK_ID = "1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so"
WORKBOOK_TITLE = "Bilqis Curriculum Registry - Version, Lessons, Prerequisites and Champion States"
WORKBOOK_URL = f"https://docs.google.com/spreadsheets/d/{WORKBOOK_ID}/edit"


def load_snapshot(slug: str) -> tuple[dict, list[list[str]]]:
    payload = json.loads((WORK / f"{slug}.json").read_text(encoding="utf-8"))
    values = payload["provider_result"].get("values") or []
    return payload, values


def rows_by_header(values: list[list[str]]) -> list[dict[str, str]]:
    if not values:
        return []
    headers = [str(value) for value in values[0]]
    rows: list[dict[str, str]] = []
    for source_row, values_row in enumerate(values[1:], start=2):
        padded = list(values_row) + [""] * (len(headers) - len(values_row))
        row = {headers[i]: str(padded[i]) if padded[i] is not None else "" for i in range(len(headers))}
        row["__source_row"] = str(source_row)
        rows.append(row)
    return rows


def index(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows if row.get(key)}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def canonical_relation(disposition: str, relation_type: str = "") -> str:
    raw = clean(disposition).upper()
    relation = clean(relation_type).upper()
    mapping = {
        "APPROVED_QUALIFIED_RELATION": "qualified_relation",
        "APPROVED_TYPED_FORMAL_ADAPTER": "formal_adapter",
        "APPROVED_NAMED_REFERENT_STRATEGY": "named_referent_strategy",
        "APPROVED_COMPOSITION_STRATEGY": "composition_strategy",
        "APPROVED_NATIVE_PROTOCOL_FUNCTION": "native_protocol_only",
        "REJECTED_EXACT_EQUIVALENCE": "rejected_exact_equivalence",
    }
    if raw in mapping:
        return mapping[raw]
    if "HISTORICAL" in raw or "HISTORICAL" in relation:
        return "historical_analogy"
    if raw or relation:
        return "proposal_or_reviewed_relation"
    return "unmapped"


def canonical_bridge_state(value: str) -> str:
    raw = clean(value).upper()
    if "BLOCKED" in raw:
        return "blocked"
    if "DEFERRED" in raw:
        return "deferred"
    if "HISTORICAL" in raw:
        return "historical_only"
    if "PROPOSED" in raw:
        return "proposal"
    if "SOURCE-SEEDED" in raw:
        return "source_seeded"
    if "RESEARCH SEED" in raw:
        return "research_seed"
    if "RESEARCH ONLY" in raw or "TRAINING NOT ACTIVE" in raw:
        return "research_only"
    return "unclassified"


def url_from_text(value: str) -> str:
    match = re.search(r"https?://[^\s,;)]+", clean(value))
    return match.group(0).rstrip(".]'") if match else ""


def resolve_source(
    raw_url: str,
    locus: str,
    manifest: list[dict[str, str]],
    sections: list[dict[str, str]],
) -> dict[str, str]:
    url = url_from_text(raw_url) or clean(raw_url)
    source_id = ""
    match_state = "unresolved"
    if url:
        for row in manifest:
            if url in {row["requested_url"], row["final_url"]}:
                source_id = row["source_id"]
                match_state = "exact_url"
                break
        if not source_id:
            basename = Path(urlsplit(url).path).name
            exact_basename = [
                row
                for row in manifest
                if basename
                and basename
                in {
                    Path(urlsplit(row["requested_url"]).path).name,
                    Path(urlsplit(row["final_url"]).path).name,
                }
            ]
            if len(exact_basename) == 1:
                source_id = exact_basename[0]["source_id"]
                match_state = "exact_case_sensitive_basename"

    historical = "2011" in (url + " " + locus) or url.endswith("/03_morphology.html")
    if historical and not source_id:
        match_state = "historical_unpinned"

    section_id = ""
    section_number = ""
    if source_id:
        matches = re.findall(r"(?:§|Sec\.?|Section)\s*(\d+(?:\.\d+)+)", locus, flags=re.I)
        if not matches:
            matches = re.findall(r"\b(\d+(?:\.\d+){1,3})\b", locus)
        for candidate in matches:
            found = next(
                (
                    row
                    for row in sections
                    if row["source_id"] == source_id and row["section_number"] == candidate
                ),
                None,
            )
            if found:
                section_id = found["section_id"]
                section_number = found["section_number"]
                break

    if section_id:
        target_kind = "source_section"
        target_id = section_id
    elif source_id:
        target_kind = "source_document"
        target_id = source_id
    elif historical:
        target_kind = "historical_source"
        target_id = ""
    else:
        target_kind = "unresolved"
        target_id = ""

    return {
        "resolved_source_id": source_id,
        "resolved_section_id": section_id,
        "resolved_section_number": section_number,
        "source_match_state": match_state,
        "target_kind": target_kind,
        "target_id": target_id,
        "source_era": "historical_2011" if historical else ("current_snapshot" if source_id else "unresolved"),
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    SOURCES.mkdir(parents=True, exist_ok=True)

    cached_specs = [
        ("token_atlas", "Token Atlas", "A1:P228"),
        ("semantic_bridges", "Semantic Bridges", "A1:L331"),
        ("token_mapping_reviews", "Token Mapping Reviews", "A1:P223"),
        ("ni_adjudication_vd", "NI Adjudication vD", "A1:L95"),
        ("lessons", "Lessons", "A1:M112"),
        ("prerequisites", "Prerequisites", "A1:L77"),
        ("decisions", "Decisions", "A1:G48"),
        ("version_coverage", "Version Coverage", "A1:L106"),
    ]
    snapshot_at = datetime.fromtimestamp(
        max((WORK / f"{slug}.json").stat().st_mtime for slug, _tab, _range in cached_specs),
        tz=timezone.utc,
    ).replace(microsecond=0).isoformat()
    manifest_rows: list[dict[str, str]] = []
    values_by_slug: dict[str, list[list[str]]] = {}
    for slug, tab, requested_range in cached_specs:
        payload, values = load_snapshot(slug)
        values_by_slug[slug] = values
        manifest_rows.append(
            {
                "workbook_id": WORKBOOK_ID,
                "workbook_title": WORKBOOK_TITLE,
                "workbook_url": WORKBOOK_URL,
                "tab": tab,
                "requested_range": requested_range,
                "returned_range": clean(str(payload["provider_result"].get("range", ""))),
                "returned_rows": str(len(values)),
                "snapshot_json_sha256": sha256(WORK / f"{slug}.json"),
                "snapshot_at_utc": snapshot_at,
                "role": "enrichment_only_no_curriculum_order",
            }
        )
    write_csv(SOURCES / "curriculum_manifest.csv", manifest_rows)

    official_manifest = load_csv(SOURCES / "source_manifest.csv")
    source_sections = load_csv(DATA / "source_sections.csv")

    atlas = index(rows_by_header(values_by_slug["token_atlas"]), "0-based Token ID")
    mapping = index(rows_by_header(values_by_slug["token_mapping_reviews"]), "Token ID")
    adjudication = index(rows_by_header(values_by_slug["ni_adjudication_vd"]), "Token ID")

    crosswalk_rows: list[dict[str, str]] = []
    for token_id in sorted(mapping, key=lambda value: int(value) if value.isdigit() else 10**9):
        review = mapping[token_id]
        v_d = adjudication.get(token_id)
        token = atlas.get(token_id, {})
        if v_d:
            source_tab = "NI Adjudication vD"
            source_row = v_d["__source_row"]
            definition = v_d.get("Source-exact semantic definition", "")
            bridge = v_d.get("Reviewed New Ithkuil anchor / strategy", "")
            official_url = v_d.get("Official Ithkuil source URL", "")
            locus = v_d.get("Official locus", "")
            differential = v_d.get("Semantic differential / non-equivalence", "")
            disposition = v_d.get("Delegated disposition", "")
            wordform_status = v_d.get("New Ithkuil wordform status", "")
            generation = v_d.get("Ledger version", "")
            crosswalk_state = "ADJUDICATED_VD"
        else:
            source_tab = "Token Mapping Reviews"
            source_row = review["__source_row"]
            definition = review.get("Proposed description", "") or review.get("Previous recorded description", "")
            bridge = review.get("Proposed New Ithkuil bridge", "")
            official_url = review.get("Source URL", "")
            locus = review.get("Primary source location", "")
            differential = review.get("Evidence / distinction", "")
            disposition = review.get("Disposition", "")
            wordform_status = "NOT_SEPARATELY_ADJUDICATED_VD"
            generation = review.get("Applied in ledger version", "") or review.get("Parent version", "")
            crosswalk_state = "MAPPING_REVIEW"

        resolution = resolve_source(official_url, locus, official_manifest, source_sections)
        crosswalk_rows.append(
            {
                "crosswalk_id": f"BILQIS-NI-{int(token_id):03d}" if token_id.isdigit() else f"BILQIS-NI-{token_id}",
                "bilqis_token_id": token_id,
                "bilqis_token_symbol": clean(token.get("Bilqis token symbol", "") or review.get("Token symbol", "")),
                "bilqis_pasigraphy_identity": clean(token.get("Pasigraphy identity", "") or review.get("Legacy pasigraphy identity", "")),
                "bilqis_source_definition": clean(definition),
                "bilqis_formal_signature": clean(token.get("Formal signature", "")),
                "bilqis_semantic_family": clean(token.get("Semantic family", "")),
                "bilqis_source_subtype": clean(token.get("Source subtype", "")),
                "bilqis_arity": clean(token.get("Arity", "")),
                "new_ithkuil_bridge": clean(bridge),
                "relation_type": clean(review.get("Relation / change type", "")),
                "equivalence_state": canonical_relation(disposition, review.get("Relation / change type", "")),
                "official_source_url": clean(official_url),
                "official_locus": clean(locus),
                **resolution,
                "semantic_differential": clean(differential),
                "mapping_disposition": clean(disposition),
                "new_ithkuil_wordform_status": clean(wordform_status),
                "review_generation": clean(generation),
                "crosswalk_state": crosswalk_state,
                "source_tab": source_tab,
                "source_row": source_row,
                "mapping_review_id": clean(review.get("Revision ID", "")),
            }
        )
    write_csv(DATA / "bilqis_ithkuil_crosswalk.csv", crosswalk_rows)

    bridge_rows: list[dict[str, str]] = []
    for row in rows_by_header(values_by_slug["semantic_bridges"]):
        bridge_id = clean(row.get("Bridge ID", ""))
        if not bridge_id:
            continue
        primary_source = clean(row.get("Primary source", ""))
        locus = clean(row.get("Source locus / era", ""))
        registry_state = clean(row.get("Status / gate", ""))
        resolution = resolve_source(primary_source, locus, official_manifest, source_sections)
        bridge_rows.append(
            {
                "bridge_id": bridge_id,
                "source_locus_or_era": locus,
                "ithkuil_category_or_root": clean(row.get("Ithkuil category / root", "")),
                "source_grounded_semantic_meaning": clean(row.get("Source-grounded semantic meaning", "")),
                "link_type": clean(row.get("Link type", "")),
                "registry_state_raw": registry_state,
                "bridge_epistemic_state": canonical_bridge_state(registry_state),
                "primary_source": primary_source,
                **resolution,
                "semantic_caution_or_dependencies": clean(row.get("Semantic caution / dependencies", "")),
                "source_tab": "Semantic Bridges",
                "source_row": row["__source_row"],
            }
        )
    write_csv(DATA / "bilqis_semantic_bridges.csv", bridge_rows)

    print(
        f"curriculum_tabs={len(manifest_rows)} crosswalk={len(crosswalk_rows)} "
        f"adjudicated_vd={sum(row['crosswalk_state'] == 'ADJUDICATED_VD' for row in crosswalk_rows)} "
        f"semantic_bridges={len(bridge_rows)}"
    )


if __name__ == "__main__":
    main()

