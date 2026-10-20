#!/usr/bin/env python3
"""Validate structural, provenance, and experiment-boundary invariants."""

from __future__ import annotations

import csv
import re
import subprocess
from collections import Counter
from pathlib import Path

from lxml import html


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data" / "csv"
SOURCES = DATA / "sources"


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
    lexicon_roots = read_csv(DATA / "lexicon_roots.csv")
    lexicon_senses = read_csv(DATA / "lexicon_root_senses.csv")
    allomorph_rules = read_csv(DATA / "allomorph_rules.csv")
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
    lexicon_root_ids = unique_ids(lexicon_roots, "lexicon_root_id", "lexicon roots")
    unique_ids(lexicon_senses, "lexicon_sense_id", "lexicon root senses")
    unique_ids(allomorph_rules, "allomorph_rule_id", "allomorph rules")
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
        header_length = int(row["header_value_char_count"])
        if header_length > 200:
            require(row["header_value"] == "", "long source header copied verbatim into tracked cell ledger")
            require(row["header_value_truncated"] == "true", "long source header lacks truncation marker")

    for row in tables:
        header_length = int(row["header_char_count"])
        if header_length > 200:
            require(row["header_text"] == "", "long source table header copied verbatim into tracked dataset")
            require(row["header_text_truncated"] == "true", "long source table header lacks truncation marker")
        require(len(row["context_label"]) <= 180, "source table context label exceeds compact locator limit")

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
    require(len(lexicon_roots) == 503, f"expected 503 Chapter-1/2 lexicon roots, found {len(lexicon_roots)}")
    require(len(lexicon_senses) == 1530, f"expected 1,530 Chapter-1/2 lexicon senses, found {len(lexicon_senses)}")
    require(all(row["source_id"] == "NI-LEXICON-CURRICULUM" for row in lexicon_roots), "lexicon root source identity drift")
    require(all(row["lexicon_root_id"] in lexicon_root_ids for row in lexicon_senses), "lexicon sense references unknown lexicon root")
    require(all(row["source_id"] == "NI-LEXICON-CURRICULUM" for row in lexicon_senses), "lexicon sense source identity drift")
    require(all(row["tracked_pdf_sha256"] for row in lexicon_roots + lexicon_senses), "lexicon extraction row lost tracked split-PDF identity")
    lexicon_root_by_form = {row["root_form_raw"]: row for row in lexicon_roots}
    require(lexicon_root_by_form["-Č-"]["lexicon_section"] == "1.3", "copular root lost Chapter 1.3 locus")
    require(lexicon_root_by_form["-PS-"]["lexicon_section"] == "2.0", "event root lost Chapter 2.0 locus")
    copular_senses = [row for row in lexicon_senses if row["root_form_raw"] == "-Č-"]
    require(len(copular_senses) == 12, "copular root must preserve its 3-stem x 4-Specification matrix")
    require(all(row["source_id"] in source_ids for row in allomorph_rules), "allomorph rule references unknown source")
    require(all(not row["section_id"] or row["section_id"] in section_ids for row in allomorph_rules), "allomorph rule section FK failure")
    require(all(not row["table_id"] or row["table_id"] in table_ids for row in allomorph_rules), "allomorph rule table FK failure")

    def unique_value_codes(family: str) -> set[str]:
        return {row["value_code"] for row in atomic if row["morpheme_family"] == family}

    require(len(unique_value_codes("case")) == 68, "case inventory must contain exactly 68 semantic case identities")
    require(len(unique_value_codes("configuration")) == 20, "configuration inventory must contain exactly 20 values")
    require(len(unique_value_codes("valence")) == 9, "valence inventory must contain exactly 9 values")
    require(len(unique_value_codes("phase")) == 9, "phase inventory must contain exactly 9 values")
    require(len(unique_value_codes("effect")) == 9, "effect inventory must contain exactly 9 values")
    require(len(unique_value_codes("level")) == 9, "level inventory must contain exactly 9 values")
    require(len(unique_value_codes("aspect")) == 36, "aspect inventory must contain exactly 36 values")
    require(len(unique_value_codes("affix_vowel")) == 30, "V_X inventory must contain 3 types x 10 degrees")
    require(len(unique_value_codes("referential")) == 33, "referential inventory must contain 11 referents x 3 effects")
    require(len(unique_value_codes("bias_adjunct")) == 61, "bias inventory must contain 61 fixed adjuncts")
    require(len(unique_value_codes("specialized_root")) == 74, "Chapter 10 specialized-root inventory must contain 74 roots")
    require(len(unique_value_codes("number_root")) == 20, "number-root inventory must contain 20 source-listed roots")
    require(len(unique_value_codes("function_specification_context")) == 32, "Slot-IV V_R matrix must contain 32 Function×Specification×Context identities")
    require(sum(row["morpheme_family"] == "function_specification_context" for row in atomic) == 40, "Slot-IV V_R matrix must retain eight conditioned RPS allomorph surfaces")
    register_initial = [row for row in atomic if row["morpheme_family"] == "register_adjunct_initial"]
    register_final = [row for row in atomic if row["morpheme_family"] == "register_adjunct_final"]
    expected_register_initial_codes = {"NRR", "DSV", "PNT", "SPF", "EXM", "CGT"}
    expected_register_final_codes = expected_register_initial_codes | {"END"}
    require({row["value_code"] for row in register_initial} == expected_register_initial_codes, "register initial-adjunct inventory drift")
    require({row["value_code"] for row in register_final} == expected_register_final_codes, "register final-adjunct inventory drift")
    suppletive_codes = {row["value_code"] for row in atomic if row["morpheme_family"] == "suppletive_adjunct_cp"}
    require(suppletive_codes == {"CAR", "QUO", "NAM", "PHR"}, "suppletive C_P inventory drift")
    number_codes = unique_value_codes("number_root")
    require({"NUM.100^2", "NUM.100^4", "NUM.100^8"} <= number_codes, "Chapter 13 exponent-style number labels were not normalized")
    validation_codes = unique_value_codes("validation")
    require(
        validation_codes == {"OBS", "REC", "PUP", "RPR", "USP", "IMA", "CVN", "ITU", "INF"},
        f"validation inventory does not match Chapter 6 T4: {sorted(validation_codes)}",
    )
    illocution_codes = unique_value_codes("illocution")
    require(
        illocution_codes == {"ASR", "DIR", "DEC", "IRG", "VER", "ADM", "POT", "HOR", "CNJ"},
        f"illocution inventory does not match Chapter 6 T4: {sorted(illocution_codes)}",
    )
    require(all(row["value_code"] for row in atomic), "atomic morpheme has blank value_code")
    require(
        not any(re.search(r"\s", row["surface_form_raw"]) for row in atomic),
        "atomic surface form contains whitespace/HTML-run artifact",
    )
    validate_ch5_vn_matrix(atomic)
    validate_ch6_vk_matrix(atomic)
    validate_slot_iv_vr_matrix(atomic)
    validate_register_matrix(atomic)
    require(not any("*" in row["surface_form_raw"] for row in atomic), "source footnote marker leaked into an atomic surface form")
    upx = [row for row in atomic if row["morpheme_family"] == "configuration" and row["value_code"] == "UPX"]
    require(len(upx) == 1 and upx[0]["surface_form_raw"] == "∅", "UPX must be zero/unmarked, not a footnote marker")
    referential_footnote_forms = {"lç", "rç", "řç", "mç", "nç", "ňç"}
    actual_referential_footnote_forms = {
        row["surface_form_normalized"]
        for row in atomic
        if row["morpheme_family"] == "referential" and row["realization_type"] == "conditioned_allomorph"
    }
    require(actual_referential_footnote_forms == referential_footnote_forms, "referential conditioned-allomorph inventory drift")
    for row in atomic:
        if row["morpheme_family"] == "referential" and row["surface_form_normalized"] in referential_footnote_forms:
            require(
                row["allomorph_condition"] == "Referential Affixes only; used to avoid ambiguity with geminated C_A forms",
                f"referential footnote condition lost for {row['surface_form_raw']}",
            )
    case_rows = [row for row in atomic if row["morpheme_family"] == "case"]
    require(all(row["primary_section_id"] and row["primary_source_line"] for row in case_rows), "case atom lost Chapter 4 section/line provenance")
    require(len(allomorph_rules) == 19, f"expected 19 explicit C_A allomorphic substitutions, found {len(allomorph_rules)}")
    expected_ca_rules = {
        ("pp", "", "mp"), ("pb", "", "mb"), ("rr", "", "ns"), ("[C]gm", "", "[C]x"),
        ("[C]bm", "", "[C]v"), ("tt", "", "nt"), ("kg", "", "ng"), ("rř", "", "nš"),
        ("[C]gn", "", "[C]ň"), ("[C]bn", "", "[C]ḑ"), ("kk", "", "nk"), ("çy", "", "nd"),
        ("řr", "", "ňs"), ("ngn", "", "ňn"), ("fbm", "fv", "vw"), ("ll", "", "pļ"),
        ("řř", "", "ňš"), ("[C]çx", "", "[C]xw"), ("ţbn", "tḑ", "ḑy"),
    }
    actual_ca_rules = {(row["input_pattern"], row["intermediate_pattern"], row["output_pattern"]) for row in allomorph_rules}
    require(actual_ca_rules == expected_ca_rules, "C_A allomorphic substitution inventory drift")
    expected_ca_trigger = "immediately preceded by consonant+t, consonant+p, or consonant+k"
    expected_ca_default = "default; use {alternate} when immediately preceded by consonant+t, consonant+p, or consonant+k"
    for value_code, primary, alternate in (("N.RPV", "m", "h"), ("A.RPV", "n", "ç")):
        matched_alt = [row for row in atomic if row["morpheme_family"] == "perspective_essence" and row["value_code"] == value_code and row["surface_form_normalized"] == alternate]
        matched_primary = [row for row in atomic if row["morpheme_family"] == "perspective_essence" and row["value_code"] == value_code and row["surface_form_normalized"] == primary]
        require(len(matched_alt) == 1 and matched_alt[0]["allomorph_condition"] == expected_ca_trigger, f"exact C_A trigger lost for {value_code}->{alternate}")
        require(len(matched_primary) == 1 and matched_primary[0]["allomorph_condition"] == expected_ca_default.format(alternate=alternate), f"exact C_A default condition lost for {value_code}->{primary}")
    validate_case_forms_against_source(atomic, sections)

    sense_counts = Counter(row["table_id"] for row in senses)
    expected_sense_counts = {
        "NI-WEB-CH02:T007": 12,
        "NI-WEB-CH02:T008": 12,
        "NI-WEB-APP:T008": 6,
        "NI-WEB-APP:T009": 6,
        "NI-WEB-APP:T010": 6,
        "NI-WEB-APP:T011": 6,
        "NI-WEB-CH10:T003": 12,
        "NI-WEB-CH10:T011": 6,
        "NI-WEB-CH10:T012": 6,
        "NI-WEB-CH10:T013": 6,
    }
    for table_id, expected in expected_sense_counts.items():
        require(sense_counts[table_id] == expected, f"explicit root-paradigm sense coverage drift at {table_id}: {sense_counts[table_id]} != {expected}")
    validate_root_paradigm_identities(atomic, senses)

    comp_types = Counter(row["composition_type"] for row in compositions)
    require(comp_types["VXCS_affix"] >= 1000, "expected at least 1,000 V_XC_S source-join forms")
    require(comp_types["case_accessor"] >= 204, "case-accessor coverage below 68 cases x 3 types")
    require(comp_types["inverse_case_accessor"] >= 204, "inverse case-accessor coverage below 68 cases x 3 types")
    require(comp_types["case_stacking"] >= 68, "case-stacking coverage below 68 cases")
    require(comp_types["suppletive_adjunct"] == 272, f"expected 272 C_P+V_C suppletive-adjunct source joins, found {comp_types['suppletive_adjunct']}")
    suppletive_rows = [row for row in compositions if row["composition_type"] == "suppletive_adjunct"]
    require(len({row["value_code"] for row in suppletive_rows}) == 272, "suppletive adjunct case identities are duplicated or missing")
    require(
        all(not row["surface_form_raw"].endswith("’") for row in suppletive_rows),
        "suppletive adjunct emitted an underlying word-final glottal V_C form",
    )
    suppletive_ids = {row["composition_id"] for row in suppletive_rows}
    suppletive_case_components = [
        row for row in components
        if row["composition_id"] in suppletive_ids and row["component_role"] == "case exponent"
    ]
    require(len(suppletive_case_components) == 272, "suppletive adjunct case-component count drift")
    for component in suppletive_case_components:
        atom = next(row for row in atomic if row["atomic_id"] == component["atomic_id"])
        require(atom["realization_type"] != "conditioned_allomorph", "suppletive adjunct used an impossible y/w-conditioned V_C alternant")
        require(atom["realization_type"] != "underlying_glottal", "suppletive adjunct used an underlying word-final glottal V_C form")

    require(all(row["target_kind"] in {"source_document", "source_section"} for row in crosswalk), "token crosswalk contains unresolved source target")
    bridge_targets = Counter(row["target_kind"] for row in bridges)
    require(bridge_targets["historical_source"] == 2, "expected exactly two historical-only 2011 semantic bridges")
    require(bridge_targets["unresolved"] == 0, "semantic bridge contains unexplained unresolved target")
    require(all(row["registry_state_raw"] for row in bridges), "semantic bridge registry status/gate was dropped")
    bridge_states = Counter(row["bridge_epistemic_state"] for row in bridges)
    require(bridge_states["blocked"] == 1, "expected one explicitly blocked semantic bridge")
    require(bridge_states["deferred"] == 1, "expected one explicitly deferred semantic bridge")
    require(bridge_states["proposal"] >= 17, "proposal-only semantic bridge state was lost")
    require(any(row["equivalence_state"] == "rejected_exact_equivalence" for row in crosswalk), "negative/non-equivalent crosswalk evidence was lost")

    banned_curriculum_order_columns = {
        "grade",
        "lesson",
        "lesson_order",
        "tranche",
        "champion",
        "mastery",
        "curriculum_order",
        "teaching_order",
        "pedagogical_order",
        "rank",
    }
    for path in sorted(DATA.glob("*.csv")):
        headers = set(read_csv_headers(path))
        leaked = headers & banned_curriculum_order_columns
        require(not leaked, f"curriculum-order column leaked into {path.name}: {leaked}")

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
    require(not any("/_raw/" in path or "/_private/" in path for path in tracked), "raw or authenticated private cache is tracked by Git")

    print(
        "validation=PASS "
        f"sources={len(manifest)} sections={len(sections)} tables={len(tables)} cells={len(cells)} "
        f"atomic={len(atomic)} compositions={len(compositions)} components={len(components)} assertions={len(assertions)} "
        f"categories={len(categories)} affix_degrees={len(degrees)} root_senses={len(senses)} allomorph_rules={len(allomorph_rules)} "
        f"crosswalk={len(crosswalk)} bridges={len(bridges)}"
    )


def read_csv_headers(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def source_table_rows(filename: str, table_index: int) -> list[list[str]]:
    tree = html.parse(str(ROOT / "_raw" / filename))
    table = tree.xpath("//table")[table_index - 1]
    return [
        [" ".join(" ".join(cell.itertext()).split()) for cell in tr.xpath("./th|./td")]
        for tr in table.xpath(".//tr")
    ]


def normalize_surface(value: str) -> str:
    value = value.replace("’", "'").replace("‘", "'").lower()
    value = re.sub(r"\s*\*+\s*", " ", value)
    value = value.strip().strip("()")
    value = re.sub(r"^[-–—]\s*", "", value)
    value = re.sub(r"\s*[-–—]$", "", value)
    value = re.sub(r"\s+", "", value)
    return value or "∅"


def source_surface_set(value: str) -> set[str]:
    cleaned = re.sub(r"\s*\*+\s*", " ", value).strip()
    if cleaned in {"", "-", "—", "Ø", "∅"}:
        return {"∅"}
    if re.fullmatch(r"\(([^)]+)\)", cleaned):
        cleaned = cleaned[1:-1]
    return {normalize_surface(part) for part in cleaned.split("/") if part.strip()}


def family_surface_map(atomic: list[dict[str, str]], family: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in atomic:
        if row["morpheme_family"] == family:
            out.setdefault(row["value_code"], set()).add(row["surface_form_normalized"])
    return out


def validate_ch5_vn_matrix(atomic: list[dict[str, str]]) -> None:
    rows = source_table_rows("newithkuil_05_verbs.htm", 3)
    expected: dict[str, dict[str, set[str]]] = {family: {} for family in ("valence", "phase", "effect", "level")}
    columns = {
        "valence": (1, 2),
        "phase": (4, 5),
        "effect": (7, 8),
        "level": (10, 11),
    }
    for row in rows[2:]:
        for family, (code_col, form_col) in columns.items():
            if len(row) <= form_col or not row[code_col]:
                continue
            expected[family][row[code_col]] = source_surface_set(row[form_col])
    for family, expected_map in expected.items():
        actual_map = family_surface_map(atomic, family)
        require(actual_map == expected_map, f"Chapter 5 T3 {family} code→surface mapping drift: {actual_map} != {expected_map}")


def validate_ch6_vk_matrix(atomic: list[dict[str, str]]) -> None:
    rows = source_table_rows("newithkuil_06_more_verbs.htm", 4)
    expected_validation: dict[str, set[str]] = {}
    expected_illocution: dict[str, set[str]] = {}
    first = rows[1]
    expected_illocution[first[0].split(maxsplit=1)[0]] = source_surface_set(first[-1])
    expected_validation[first[1]] = source_surface_set(first[-1])
    for row_index, row in enumerate(rows[2:], start=3):
        if not row or not row[0]:
            continue
        if row_index <= 10:
            expected_validation[row[0].replace(" ", "")] = source_surface_set(row[-1])
        else:
            expected_illocution[row[0]] = source_surface_set(row[-1])
    require(family_surface_map(atomic, "validation") == expected_validation, "Chapter 6 T4 Validation code→surface mapping drift")
    require(family_surface_map(atomic, "illocution") == expected_illocution, "Chapter 6 T4 Illocution code→surface mapping drift")


def validate_slot_iv_vr_matrix(atomic: list[dict[str, str]]) -> None:
    rows = source_table_rows("newithkuil_03_morphology.htm", 40)
    contexts = [value.replace("*", "").strip() for value in rows[1]]
    expected: dict[str, set[str]] = {}
    function = ""
    for row in rows[2:]:
        if not row:
            continue
        if row[0] in {"STA", "DYN"}:
            function = row[0]
            specification = row[1]
            forms = row[2:6]
        else:
            specification = row[0]
            forms = row[1:5]
        for context, form in zip(contexts, forms):
            expected[f"{function}.{specification}.{context}"] = source_surface_set(form)
    actual = family_surface_map(atomic, "function_specification_context")
    require(actual == expected, "Chapter 3 T40 Slot-IV V_R code→surface mapping drift")
    for row in atomic:
        if row["morpheme_family"] != "function_specification_context" or ".RPS" not in row["value_code"]:
            continue
        if row["realization_type"] == "conditioned_allomorph":
            primary_set = expected[row["value_code"]]
            condition = row["allomorph_condition"]
            require(condition in {"immediately preceded by y", "immediately preceded by w"}, f"unexpected RPS allomorph condition: {condition}")
            require(len(primary_set) == 2, f"RPS identity {row['value_code']} lost its two source-listed surfaces")


def validate_register_matrix(atomic: list[dict[str, str]]) -> None:
    rows = source_table_rows("newithkuil_08_adjuncts.htm", 5)
    expected_initial: dict[str, set[str]] = {}
    expected_final: dict[str, set[str]] = {}
    for row in rows[1:]:
        if len(row) < 4 or not re.fullmatch(r"[A-Z]{3}", row[0]):
            continue
        code, _name, initial, final = row[:4]
        if not (code == "END" and initial in {"", "-", "—"}):
            expected_initial[code] = source_surface_set(initial)
        expected_final[code] = source_surface_set(final)
    require(family_surface_map(atomic, "register_adjunct_initial") == expected_initial, "Chapter 8 T5 register-initial mapping drift")
    require(family_surface_map(atomic, "register_adjunct_final") == expected_final, "Chapter 8 T5 register-final mapping drift")
    spf = [row for row in atomic if row["morpheme_family"] == "register_adjunct_initial" and row["value_code"] == "SPF"]
    end = [row for row in atomic if row["morpheme_family"] == "register_adjunct_final" and row["value_code"] == "END"]
    require(len(spf) == 1 and "otherwise use PNT" in spf[0]["allomorph_condition"], "SPF register footnote condition lost")
    require(len(end) == 1 and "proper name or foreign word/phrase" in end[0]["allomorph_condition"], "END register footnote condition lost")


def validate_root_paradigm_identities(atomic: list[dict[str, str]], senses: list[dict[str, str]]) -> None:
    expected_regular = {
        "NI-WEB-CH02:T007": ("dn", {("Stem 1", "BSC"), ("Stem 2", "BSC"), ("Stem 3", "BSC"), ("Stem 1", "CTE"), ("Stem 2", "CTE"), ("Stem 3", "CTE"), ("Stem 1", "CSV"), ("Stem 2", "CSV"), ("Stem 3", "CSV"), ("Stem 1", "OBJ"), ("Stem 2", "OBJ"), ("Stem 3", "OBJ")}),
        "NI-WEB-CH02:T008": ("lk", {("Stem 1", "BSC"), ("Stem 2", "BSC"), ("Stem 3", "BSC"), ("Stem 1", "CTE"), ("Stem 2", "CTE"), ("Stem 3", "CTE"), ("Stem 1", "CSV"), ("Stem 2", "CSV"), ("Stem 3", "CSV"), ("Stem 1", "OBJ"), ("Stem 2", "OBJ"), ("Stem 3", "OBJ")}),
        "NI-WEB-CH10:T003": ("s", {("STEM 1", "BSC"), ("STEM 2", "BSC"), ("STEM 3", "BSC"), ("STEM 1", "CTE"), ("STEM 2", "CTE"), ("STEM 3", "CTE"), ("STEM 1", "CSV"), ("STEM 2", "CSV"), ("STEM 3", "CSV"), ("STEM 1", "OBJ"), ("STEM 2", "OBJ"), ("STEM 3", "OBJ")}),
    }
    expected_compact_roots = {
        "NI-WEB-APP:T008": "ḑt",
        "NI-WEB-APP:T009": "llk",
        "NI-WEB-APP:T010": "ntň",
        "NI-WEB-APP:T011": "ksm",
        "NI-WEB-CH10:T011": "tr",
        "NI-WEB-CH10:T012": "ţ",
        "NI-WEB-CH10:T013": "ţf",
    }
    atoms = {row["atomic_id"]: row for row in atomic}
    for table_id, (root, expected_pairs) in expected_regular.items():
        rows = [row for row in senses if row["table_id"] == table_id]
        require({(row["stem"], row["specification"]) for row in rows} == expected_pairs, f"root sense identity drift at {table_id}")
        require({atoms[row["atomic_id"]]["surface_form_normalized"] for row in rows} == {root}, f"root identity drift at {table_id}")
    compact_pairs = {("Stem 1", "BSC"), ("Stem 1", "CTE"), ("Stem 1", "CSV"), ("Stem 1", "OBJ"), ("Stem 2", "BSC"), ("Stem 3", "BSC")}
    for table_id, root in expected_compact_roots.items():
        rows = [row for row in senses if row["table_id"] == table_id]
        require({(row["stem"], row["specification"]) for row in rows} == compact_pairs, f"compact root sense identity drift at {table_id}")
        require({atoms[row["atomic_id"]]["surface_form_normalized"] for row in rows} == {root}, f"root identity drift at {table_id}")


def validate_case_forms_against_source(atomic: list[dict[str, str]], sections: list[dict[str, str]]) -> None:
    """Require every emitted V_C surface/allomorph to occur in its Chapter 4 declaration."""
    cases: dict[str, list[dict[str, str]]] = {}
    for row in atomic:
        if row["morpheme_family"] == "case":
            cases.setdefault(row["value_code"], []).append(row)

    tree = html.parse(str(ROOT / "_raw" / "newithkuil_04_case.htm"))
    ch4_sections = sorted(
        [row for row in sections if row["source_id"] == "NI-WEB-CH04"],
        key=lambda row: int(row["source_line"] or 0),
    )
    checked = 0
    for table in tree.xpath("//table"):
        rows = table.xpath(".//tr")
        if len(rows) != 1:
            continue
        cells = [" ".join(" ".join(cell.itertext()).split()) for cell in rows[0].xpath("./th|./td")]
        if len(cells) < 3 or not re.fullmatch(r"[A-Z]{3}", cells[1]):
            continue
        code = cells[1]
        current = table.getnext()
        declaration = ""
        declaration_line = 0
        while current is not None and current.tag != "table":
            if current.tag == "p":
                text = " ".join(" ".join(current.itertext()).split())
                if "case is marked by" in text.lower():
                    declaration = text
                    declaration_line = int(current.sourceline or 0)
                    break
            current = current.getnext()
        require(declaration, f"missing Chapter 4 declaration for case {code}")
        expected_section = next(
            (
                row
                for row in reversed(ch4_sections)
                if int(row["source_line"] or 0) <= declaration_line
            ),
            None,
        )
        require(expected_section is not None, f"cannot resolve Chapter 4 subsection for case {code}")
        normalized_declaration = normalize_source_text(declaration)
        emitted = cases.get(code, [])
        require(emitted, f"no emitted case records for Chapter 4 case {code}")
        for row in emitted:
            require(
                normalize_source_text(row["surface_form_raw"]) in normalized_declaration,
                f"case form {code} {row['surface_form_raw']} absent from Chapter 4 declaration",
            )
            require(
                row["primary_section_id"] == expected_section["section_id"],
                f"case {code} points to {row['primary_section_id']} instead of declaration subsection {expected_section['section_id']}",
            )
            require(
                int(row["primary_source_line"] or 0) == declaration_line,
                f"case {code} source line {row['primary_source_line']} does not equal declaration line {declaration_line}",
            )
        checked += 1
    require(checked == 68, f"expected to cross-check 68 Chapter 4 case declarations, checked {checked}")


def normalize_source_text(value: str) -> str:
    value = value.lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"[\s\-()]", "", value)


if __name__ == "__main__":
    main()

