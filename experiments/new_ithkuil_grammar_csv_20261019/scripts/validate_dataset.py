#!/usr/bin/env python3
"""Validate structural, provenance, and experiment-boundary invariants."""

from __future__ import annotations

import csv
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES = ROOT / "sources"


class ValidationError(RuntimeError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def unique_ids(rows: list[dict[str, str]], field: str, label: str) -> set[str]:
    values = [row[field] for row in rows]
    require(all(values), f"{label}: blank {field}")
    require(len(values) == len(set(values)), f"{label}: duplicate {field}")
    return set(values)


def no_crlf(path: Path) -> None:
    require(b"\r\n" not in path.read_bytes(), f"CRLF found in {path.relative_to(ROOT)}")


def main() -> None:
    manifest = read_csv(SOURCES / "source_manifest.csv")
    curriculum_manifest = read_csv(SOURCES / "curriculum_manifest.csv")
    sections = read_csv(DATA / "source_sections.csv")
    tables = read_csv(DATA / "source_tables.csv")
    cells = read_csv(DATA / "source_table_cells.csv")
    atomic = read_csv(DATA / "morphemes_atomic.csv")
    compositions = read_csv(DATA / "morpheme_compositions.csv")
    components = read_csv(DATA / "composition_components.csv")
    assertions = read_csv(DATA / "source_assertions.csv")
    categories = read_csv(DATA / "grammatical_categories.csv")
    degrees = read_csv(DATA / "affix_degrees.csv")
    senses = read_csv(DATA / "root_senses.csv")
    crosswalk = read_csv(DATA / "bilqis_ithkuil_crosswalk.csv")
    bridges = read_csv(DATA / "bilqis_semantic_bridges.csv")

    require(len(manifest) == 18, f"expected 18 official source identities, found {len(manifest)}")
    require(len(curriculum_manifest) == 8, f"expected 8 curriculum snapshot tabs, found {len(curriculum_manifest)}")
    require(len(sections) == 337, f"expected 337 source sections, found {len(sections)}")
    require(len(tables) == 324, f"expected 324 HTML tables, found {len(tables)}")
    require(len(cells) == 5397, f"expected 5,397 non-empty table cells, found {len(cells)}")
    require(len(crosswalk) == 222, f"expected 222 token crosswalk rows, found {len(crosswalk)}")
    require(len(bridges) == 330, f"expected 330 semantic bridge rows, found {len(bridges)}")

    source_ids = unique_ids(manifest, "source_id", "source manifest")
    section_ids = unique_ids(sections, "section_id", "source sections")
    table_ids = unique_ids(tables, "table_id", "source tables")
    atomic_ids = unique_ids(atomic, "atomic_id", "atomic morphemes")
    composition_ids = unique_ids(compositions, "composition_id", "morpheme compositions")
    unique_ids(components, "component_id", "composition components")
    unique_ids(assertions, "assertion_id", "source assertions")
    unique_ids(categories, "category_id", "grammatical categories")
    unique_ids(degrees, "degree_id", "affix degrees")
    unique_ids(senses, "sense_id", "root senses")
    unique_ids(crosswalk, "crosswalk_id", "Bilqis crosswalk")
    unique_ids(bridges, "bridge_id", "semantic bridges")

    require(all(row["source_id"] in source_ids for row in sections), "source section references unknown source")
    require(all(not row["parent_section_id"] or row["parent_section_id"] in section_ids for row in sections), "source section parent FK failure")
    require(all(row["source_id"] in source_ids for row in tables), "source table references unknown source")
    require(all(not row["section_id"] or row["section_id"] in section_ids for row in tables), "source table section FK failure")
    require(all(row["table_id"] in table_ids for row in cells), "source cell table FK failure")

    for row in cells:
        length = int(row["cell_char_count"])
        if length > 200:
            require(row["cell_text"] == "", "long source cell copied verbatim into tracked dataset")
            require(row["cell_text_truncated"] == "true", "long source cell lacks truncation marker")
        else:
            require(row["cell_text_truncated"] == "false", "short source cell unexpectedly truncated")

    for row in components:
        require(row["composition_id"] in composition_ids, "component references unknown composition")
        require(not row["atomic_id"] or row["atomic_id"] in atomic_ids, "component references unknown atomic morpheme")
        require(row["atomic_id"] or row["literal_form_or_symbol"], "component has neither atomic ID nor literal symbol")
    component_counts = Counter(row["composition_id"] for row in components)
    for row in compositions:
        require(component_counts[row["composition_id"]] == int(row["component_count"]), f"component count mismatch for {row['composition_id']}")

    entity_ids = atomic_ids | composition_ids
    require(all(row["entity_id"] in entity_ids for row in assertions), "source assertion references unknown entity")
    asserted_atomic = {row["entity_id"] for row in assertions if row["entity_kind"] == "atomic_morpheme"}
    asserted_compositions = {row["entity_id"] for row in assertions if row["entity_kind"] == "morpheme_composition"}
    require(asserted_atomic == atomic_ids, "not every atomic morpheme has source assertions")
    require(asserted_compositions == composition_ids, "not every composition has source assertions")
    require(all(row["affix_root_atomic_id"] in atomic_ids for row in degrees), "affix degree references unknown atomic root")
    require(all(row["atomic_id"] in atomic_ids for row in senses), "root sense references unknown atomic root")

    def unique_value_codes(family: str) -> set[str]:
        return {row["value_code"] for row in atomic if row["morpheme_family"] == family}

    require(len(unique_value_codes("case")) == 68, "case inventory must contain exactly 68 semantic case identities")
    require(len(unique_value_codes("configuration")) == 20, "configuration inventory must contain exactly 20 values")
    require(len(unique_value_codes("aspect")) == 36, "aspect inventory must contain exactly 36 values")
    require(len(unique_value_codes("affix_vowel")) == 30, "V_X inventory must contain 3 types x 10 degrees")
    require(len(unique_value_codes("referential")) == 33, "referential inventory must contain 11 referents x 3 effects")
    require(len(unique_value_codes("bias_adjunct")) == 61, "bias inventory must contain 61 fixed adjuncts")
    require(len(unique_value_codes("specialized_root")) == 74, "Chapter 10 specialized-root inventory must contain 74 roots")
    require(len(unique_value_codes("number_root")) == 20, "number-root inventory must contain 20 source-listed roots")

    comp_types = Counter(row["composition_type"] for row in compositions)
    require(comp_types["VXCS_affix"] >= 1000, "expected at least 1,000 V_XC_S source-join forms")
    require(comp_types["case_accessor"] >= 204, "case-accessor coverage below 68 cases x 3 types")
    require(comp_types["inverse_case_accessor"] >= 204, "inverse case-accessor coverage below 68 cases x 3 types")
    require(comp_types["case_stacking"] >= 68, "case-stacking coverage below 68 cases")

    require(all(row["target_kind"] in {"source_document", "source_section"} for row in crosswalk), "token crosswalk contains unresolved source target")
    bridge_targets = Counter(row["target_kind"] for row in bridges)
    require(bridge_targets["historical_source"] == 2, "expected exactly two historical-only 2011 semantic bridges")
    require(bridge_targets["unresolved"] == 0, "semantic bridge contains unexplained unresolved target")
    require(any(row["equivalence_state"] == "rejected_exact_equivalence" for row in crosswalk), "negative/non-equivalent crosswalk evidence was lost")

    banned_primary_columns = {"grade", "lesson", "tranche", "champion", "mastery", "curriculum_order", "teaching_order", "rank"}
    for path in (DATA / "morphemes_atomic.csv", DATA / "morpheme_compositions.csv"):
        headers = set(read_csv_headers(path))
        require(not headers & banned_primary_columns, f"curriculum-order column leaked into {path.name}: {headers & banned_primary_columns}")

    for path in sorted([*DATA.glob("*.csv"), *SOURCES.glob("*.csv")]):
        no_crlf(path)
        text = path.read_text(encoding="utf-8")
        require("github.com/socr8s/private-ip" not in text, f"protected private-ip URL leaked into tracked data: {path.name}")

    tracked = subprocess.run(
        ["git", "ls-files", str(ROOT.relative_to(ROOT.parents[1]))],
        cwd=ROOT.parents[1],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    require(not any("/_raw/" in path or "/_work/" in path for path in tracked), "raw or authenticated work cache is tracked by Git")

    print(
        "validation=PASS "
        f"sources={len(manifest)} sections={len(sections)} tables={len(tables)} cells={len(cells)} "
        f"atomic={len(atomic)} compositions={len(compositions)} components={len(components)} "
        f"crosswalk={len(crosswalk)} bridges={len(bridges)}"
    )


def read_csv_headers(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


if __name__ == "__main__":
    main()

