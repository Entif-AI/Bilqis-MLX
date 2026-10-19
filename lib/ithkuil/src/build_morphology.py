#!/usr/bin/env python3
"""Build normalized New Ithkuil morpheme and composition tables.

The extractor is deliberately conservative.  It only mints atomic records
from explicit paradigms, fixed-form inventories, or source-declared roots.
Multi-morpheme records come from explicit grammar templates or source joins
whose components are independently attested.
"""

from __future__ import annotations

import csv
import hashlib
import re
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

from lxml import html


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "_raw"
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "source_manifest.csv"


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def short_meaning(value: str, limit: int = 180) -> str:
    text = clean(value)
    for marker in (" Examples:", " Example:", " e.g.,", " e.g. ", " For example", " NOTE:", " Note:"):
        if marker in text:
            text = text.split(marker, 1)[0]
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def normalize_form(value: str) -> str:
    value = clean(value).replace("’", "'").replace("‘", "'")
    value = value.strip(" -")
    value = re.sub(r"\s+", "", value)
    return value.lower()


def stable_id(prefix: str, *parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:14]
    return f"{prefix}-{digest}"


def table_matrix(table) -> list[list[str]]:
    matrix: list[list[str]] = []
    for tr in table.xpath(".//tr"):
        matrix.append([clean(" ".join(cell.itertext())) for cell in tr.xpath("./th|./td")])
    return matrix


def strip_bound_form(value: str) -> str:
    value = clean(value)
    value = re.sub(r"^[-–—]\s*", "", value)
    value = re.sub(r"\s*[-–—]$", "", value)
    # Morpheme cells sometimes acquire spaces from adjacent HTML runs
    # (e.g. `ö ë`).  Those are markup artifacts, not grammatical spaces.
    return re.sub(r"\s+", "", clean(value))


def surface_variants(value: str) -> list[tuple[str, str, str]]:
    """Return (surface, realization_type, condition) for an explicit form cell."""
    value = clean(value)
    # Asterisks in these paradigms are source footnote markers, never surface
    # characters.  Strip them before interpreting nulls or alternants.
    value = clean(re.sub(r"\s*\*+\s*", " ", value))
    if not value or value in {"—", "-", "Ø", "∅"}:
        return [("∅", "zero", "default or unmarked value")]
    value = value.strip()
    parenthetical = re.fullmatch(r"\(([^)]+)\)", value)
    if parenthetical:
        value = parenthetical.group(1)
        return [(strip_bound_form(value), "overt_optional", "source lists form parenthetically")]
    if "/" not in value:
        return [(strip_bound_form(value), "overt", "")]

    raw_parts = [strip_bound_form(part) for part in value.split("/") if strip_bound_form(part)]
    if len(raw_parts) != 2:
        return [(strip_bound_form(value), "overt", "source-listed compound or alternation")]
    primary, alternate = raw_parts
    primary_norm = normalize_form(primary)
    if primary_norm.startswith("i"):
        return [
            (primary, "overt", "default; replaced by listed alternant when immediately preceded by y"),
            (alternate, "conditioned_allomorph", "immediately preceded by y"),
        ]
    if primary_norm.startswith("u"):
        return [
            (primary, "overt", "default; replaced by listed alternant when immediately preceded by w"),
            (alternate, "conditioned_allomorph", "immediately preceded by w"),
        ]
    return [
        (primary, "overt", "source-listed primary form"),
        (alternate, "conditioned_allomorph", "source-listed alternant; see source locus"),
    ]


class Builder:
    def __init__(self) -> None:
        self.manifest = self._load_manifest()
        self.source_by_id = {row["source_id"]: row for row in self.manifest}
        self.trees: dict[str, html.HtmlElement] = {}
        self.sections = self._load_sections()
        self.table_loci = self._load_table_loci()
        self.atomic: dict[str, dict[str, str]] = {}
        self.atomic_key_to_id: dict[tuple[str, ...], str] = {}
        self.compositions: dict[str, dict[str, str]] = {}
        self.composition_key_to_id: dict[tuple[str, ...], str] = {}
        self.components: dict[str, dict[str, str]] = {}
        self.assertions: dict[str, dict[str, str]] = {}
        self.affix_degrees: dict[str, dict[str, str]] = {}
        self.root_senses: dict[str, dict[str, str]] = {}
        self.allomorph_rules: dict[str, dict[str, str]] = {}
        self.categories: dict[str, dict[str, str]] = {}
        self.affix_roots: dict[str, dict[str, str]] = {}
        self.vx_by_degree_type: dict[tuple[int, int], list[str]] = defaultdict(list)

    def _load_manifest(self) -> list[dict[str, str]]:
        with MANIFEST.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _load_sections(self) -> dict[str, list[dict[str, str]]]:
        out: dict[str, list[dict[str, str]]] = defaultdict(list)
        with (DATA / "source_sections.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                out[row["source_id"]].append(row)
        for rows in out.values():
            rows.sort(key=lambda row: int(row["source_line"] or 0))
        return out

    def _load_table_loci(self) -> dict[str, dict[str, str]]:
        with (DATA / "source_tables.csv").open(newline="", encoding="utf-8") as handle:
            return {row["table_id"]: row for row in csv.DictReader(handle)}

    def tree(self, source_id: str):
        if source_id not in self.trees:
            local_name = self.source_by_id[source_id]["local_name"]
            self.trees[source_id] = html.parse(str(RAW / local_name))
        return self.trees[source_id]

    def table(self, source_id: str, table_index: int):
        return self.tree(source_id).xpath("//table")[table_index - 1]

    def table_rows(self, source_id: str, table_index: int) -> list[list[str]]:
        return table_matrix(self.table(source_id, table_index))

    def section_for_line(self, source_id: str, line: int) -> dict[str, str] | None:
        rows = self.sections.get(source_id, [])
        if not rows:
            return None
        starts = [int(row["source_line"] or 0) for row in rows]
        index = bisect_right(starts, line) - 1
        return rows[index] if index >= 0 else None

    def locator_for_table(self, source_id: str, table_index: int) -> dict[str, str]:
        table_id = f"{source_id}:T{table_index:03d}"
        row = self.table_loci[table_id]
        return {
            "source_id": source_id,
            "section_id": row["section_id"],
            "table_id": table_id,
            "source_line": row["source_line"],
            "source_url": row["source_url"],
            "source_anchor": row["source_anchor"],
        }

    def locator_for_element(self, source_id: str, element) -> dict[str, str]:
        line = int(element.sourceline or 0)
        section = self.section_for_line(source_id, line)
        source = self.source_by_id[source_id]
        return {
            "source_id": source_id,
            "section_id": section["section_id"] if section else "",
            "table_id": "",
            "source_line": str(line),
            "source_url": source["final_url"],
            "source_anchor": section["source_anchor"] if section else "",
        }

    def category(self, family: str, code: str, name: str, summary: str, locator: dict[str, str]) -> str:
        category_id = stable_id("CAT", family, code or name)
        if category_id not in self.categories:
            self.categories[category_id] = {
                "category_id": category_id,
                "family": family,
                "category_code": code,
                "category_name": name,
                "description_summary": short_meaning(summary),
                **locator,
            }
        return category_id

    def add_assertion(
        self,
        entity_kind: str,
        entity_id: str,
        assertion_kind: str,
        locator: dict[str, str],
        note: str = "",
    ) -> None:
        assertion_id = stable_id(
            "AST",
            entity_kind,
            entity_id,
            assertion_kind,
            locator.get("source_id", ""),
            locator.get("table_id", ""),
            locator.get("source_line", ""),
            note,
        )
        self.assertions.setdefault(
            assertion_id,
            {
                "assertion_id": assertion_id,
                "entity_kind": entity_kind,
                "entity_id": entity_id,
                "assertion_kind": assertion_kind,
                "note": short_meaning(note, 220),
                **locator,
                "evidence_status": "official_source_observed",
            },
        )

    def add_atomic(
        self,
        *,
        surface: str,
        family: str,
        morpheme_class: str,
        slot: str = "",
        category_code: str = "",
        category_name: str = "",
        value_code: str = "",
        value_name: str = "",
        semantic_summary: str = "",
        realization_type: str = "overt",
        allomorph_condition: str = "",
        allomorph_group: str = "",
        derivation: str = "source_table",
        locator: dict[str, str],
        assertion_kind: str = "form_value",
    ) -> str:
        surface = clean(surface) or "∅"
        normalized = normalize_form(surface)
        group = allomorph_group or stable_id("AG", family, category_code, value_code or value_name)
        key = (
            family,
            morpheme_class,
            category_code,
            value_code,
            normalized,
            realization_type,
            allomorph_condition,
        )
        atomic_id = self.atomic_key_to_id.get(key)
        if atomic_id is None:
            atomic_id = stable_id("ATOM", *key)
            self.atomic_key_to_id[key] = atomic_id
            self.atomic[atomic_id] = {
                "atomic_id": atomic_id,
                "surface_form_raw": surface,
                "surface_form_normalized": normalized,
                "morpheme_family": family,
                "morpheme_class": morpheme_class,
                "slot": slot,
                "category_code": category_code,
                "category_name": category_name,
                "value_code": value_code,
                "value_name": value_name,
                "semantic_summary": short_meaning(semantic_summary),
                "realization_type": realization_type,
                "allomorph_group_id": group,
                "allomorph_condition": allomorph_condition,
                "derivation": derivation,
                "primary_source_id": locator["source_id"],
                "primary_section_id": locator["section_id"],
                "primary_table_id": locator["table_id"],
                "primary_source_line": locator["source_line"],
                "primary_source_url": locator["source_url"],
                "primary_source_anchor": locator["source_anchor"],
                "evidence_status": "official_source_observed",
            }
            self.category(family, category_code, category_name, semantic_summary, locator)
        self.add_assertion("atomic_morpheme", atomic_id, assertion_kind, locator)
        return atomic_id

    def add_composition(
        self,
        *,
        composition_type: str,
        construction_name: str,
        surface: str = "",
        surface_pattern: str = "",
        slot: str = "",
        category_code: str = "",
        category_name: str = "",
        value_code: str = "",
        value_name: str = "",
        semantic_summary: str = "",
        condition: str = "",
        derivation: str,
        locator: dict[str, str],
        components: list[dict[str, str]] | None = None,
        assertion_kind: str = "composition_rule",
    ) -> str:
        components = components or []
        component_signature = "|".join(
            f"{item.get('role','')}:{item.get('atomic_id','')}:{item.get('literal','')}:{item.get('slot','')}"
            for item in components
        )
        key = (
            composition_type,
            category_code,
            value_code,
            normalize_form(surface),
            clean(surface_pattern),
            component_signature,
            condition,
        )
        composition_id = self.composition_key_to_id.get(key)
        if composition_id is None:
            composition_id = stable_id("COMP", *key)
            self.composition_key_to_id[key] = composition_id
            self.compositions[composition_id] = {
                "composition_id": composition_id,
                "surface_form_raw": clean(surface),
                "surface_form_normalized": normalize_form(surface) if surface else "",
                "surface_pattern": clean(surface_pattern),
                "composition_type": composition_type,
                "construction_name": construction_name,
                "slot": slot,
                "category_code": category_code,
                "category_name": category_name,
                "value_code": value_code,
                "value_name": value_name,
                "semantic_summary": short_meaning(semantic_summary),
                "component_count": str(len(components)),
                "condition": condition,
                "derivation": derivation,
                "primary_source_id": locator["source_id"],
                "primary_section_id": locator["section_id"],
                "primary_table_id": locator["table_id"],
                "primary_source_line": locator["source_line"],
                "primary_source_url": locator["source_url"],
                "primary_source_anchor": locator["source_anchor"],
                "evidence_status": "official_source_observed" if derivation != "source_join" else "official_source_join",
            }
            for index, item in enumerate(components, start=1):
                component_id = stable_id("CC", composition_id, index, item)
                self.components[component_id] = {
                    "component_id": component_id,
                    "composition_id": composition_id,
                    "position_in_form": str(index),
                    "component_role": item.get("role", ""),
                    "atomic_id": item.get("atomic_id", ""),
                    "literal_form_or_symbol": item.get("literal", ""),
                    "slot_label": item.get("slot", ""),
                    "condition": item.get("condition", ""),
                }
        self.add_assertion("morpheme_composition", composition_id, assertion_kind, locator)
        return composition_id

    def add_root_sense(
        self,
        atomic_id: str,
        stem: str,
        specification: str,
        summary: str,
        locator: dict[str, str],
    ) -> None:
        sense_id = stable_id("SENSE", atomic_id, stem, specification, summary)
        self.root_senses.setdefault(
            sense_id,
            {
                "sense_id": sense_id,
                "atomic_id": atomic_id,
                "stem": stem,
                "specification": specification,
                "sense_summary": short_meaning(summary),
                **locator,
            },
        )

    def add_affix_degree(self, atomic_id: str, degree: int, summary: str, locator: dict[str, str]) -> None:
        degree_id = stable_id("DEG", atomic_id, degree, summary)
        self.affix_degrees.setdefault(
            degree_id,
            {
                "degree_id": degree_id,
                "affix_root_atomic_id": atomic_id,
                "degree": str(degree),
                "meaning_summary": short_meaning(summary),
                **locator,
            },
        )

    def add_allomorph_rule(
        self,
        *,
        domain: str,
        input_pattern: str,
        output_pattern: str,
        locator: dict[str, str],
        intermediate_pattern: str = "",
        condition_summary: str = "",
    ) -> None:
        rule_id = stable_id("ALLO", domain, input_pattern, intermediate_pattern, output_pattern, condition_summary)
        self.allomorph_rules.setdefault(
            rule_id,
            {
                "allomorph_rule_id": rule_id,
                "domain": domain,
                "input_pattern": input_pattern,
                "intermediate_pattern": intermediate_pattern,
                "output_pattern": output_pattern,
                "condition_summary": condition_summary,
                **locator,
            },
        )

    def write(self) -> None:
        write_csv(DATA / "morphemes_atomic.csv", sorted(self.atomic.values(), key=lambda row: row["atomic_id"]))
        write_csv(DATA / "morpheme_compositions.csv", sorted(self.compositions.values(), key=lambda row: row["composition_id"]))
        write_csv(DATA / "composition_components.csv", sorted(self.components.values(), key=lambda row: (row["composition_id"], int(row["position_in_form"]))))
        write_csv(DATA / "source_assertions.csv", sorted(self.assertions.values(), key=lambda row: row["assertion_id"]))
        write_csv(DATA / "grammatical_categories.csv", sorted(self.categories.values(), key=lambda row: row["category_id"]))
        write_csv(DATA / "affix_degrees.csv", sorted(self.affix_degrees.values(), key=lambda row: row["degree_id"]))
        write_csv(DATA / "root_senses.csv", sorted(self.root_senses.values(), key=lambda row: row["sense_id"]))
        write_csv(DATA / "allomorph_rules.csv", sorted(self.allomorph_rules.values(), key=lambda row: row["allomorph_rule_id"]))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def add_variants(
    b: Builder,
    *,
    form: str,
    family: str,
    morpheme_class: str,
    locator: dict[str, str],
    slot: str = "",
    category_code: str = "",
    category_name: str = "",
    value_code: str = "",
    value_name: str = "",
    semantic_summary: str = "",
    allomorph_group: str = "",
    alternate_condition: str = "",
    derivation: str = "source_table",
) -> list[str]:
    group = allomorph_group or stable_id("AG", family, category_code, value_code or value_name)
    ids: list[str] = []
    for surface, realization, condition in surface_variants(form):
        if realization == "conditioned_allomorph" and alternate_condition:
            condition = alternate_condition
        ids.append(
            b.add_atomic(
                surface=surface,
                family=family,
                morpheme_class=morpheme_class,
                slot=slot,
                category_code=category_code,
                category_name=category_name,
                value_code=value_code,
                value_name=value_name,
                semantic_summary=semantic_summary,
                realization_type=realization,
                allomorph_condition=condition,
                allomorph_group=group,
                derivation=derivation,
                locator=locator,
            )
        )
    return ids


def extract_standard_vowels(b: Builder) -> None:
    rows = b.table_rows("NI-WEB-CH02", 2)
    locator = b.locator_for_table("NI-WEB-CH02", 2)
    for row_index, row in enumerate(rows[1:], start=1):
        form_number = row_index
        for series_index, form in enumerate(row[1:], start=1):
            value_code = f"SERIES{series_index}.FORM{form_number}"
            ids = add_variants(
                b,
                form=form,
                family="standard_vowel_sequence",
                morpheme_class="vocalic_exponent",
                locator=locator,
                category_code=f"SERIES{series_index}",
                category_name=f"Standard vowel sequence series {series_index}",
                value_code=value_code,
                value_name=f"Form {form_number}",
                semantic_summary=f"Standard vowel-form sequence series {series_index}, form {form_number}",
            )
            if series_index <= 3:
                for atomic_id in ids:
                    b.atomic[atomic_id]["slot"] = "generic vowel-form"


def extract_ch3_ca(b: Builder) -> None:
    config_locator = b.locator_for_table("NI-WEB-CH03", 3)
    rows = b.table_rows("NI-WEB-CH03", 3)
    for row in rows:
        for offset in (0, 4):
            if len(row) <= offset + 2:
                continue
            code, name, form = row[offset : offset + 3]
            if not code or not name:
                continue
            add_variants(
                b,
                form=form,
                family="configuration",
                morpheme_class="CA_consonantal_exponent",
                slot="VI / C_A complex",
                locator=config_locator,
                category_code="CONFIGURATION",
                category_name="Configuration",
                value_code=code,
                value_name=name,
                semantic_summary=f"Configuration value {name}",
            )

    ca_locator = b.locator_for_table("NI-WEB-CH03", 35)
    affiliation = [
        ("CSL", "consolidative", [("∅", "zero", "default/unmarked" )]),
        ("ASO", "associative", [("l", "overt", "inside C_A complex"), ("nļ", "standalone_allomorph", "sole exponent in C_A complex")]),
        ("COA", "coalescent", [("r", "overt", "inside C_A complex"), ("rļ", "standalone_allomorph", "sole exponent in C_A complex")]),
        ("VAR", "variative", [("ř", "overt", "inside C_A complex"), ("ň", "standalone_allomorph", "sole exponent in C_A complex")]),
    ]
    for code, name, variants in affiliation:
        group = stable_id("AG", "affiliation", code)
        for form, realization, condition in variants:
            b.add_atomic(
                surface=form,
                family="affiliation",
                morpheme_class="CA_consonantal_exponent",
                slot="VI / C_A complex",
                category_code="AFFILIATION",
                category_name="Affiliation",
                value_code=code,
                value_name=name,
                semantic_summary=f"Affiliation value {name}",
                realization_type=realization,
                allomorph_condition=condition,
                allomorph_group=group,
                locator=ca_locator,
            )

    extensions = [
        ("DEL", "delimitive", [("∅", "zero", "default/unmarked")]),
        ("PRX", "proximal", [("t", "overt", "configuration overt"), ("d", "conditioned_allomorph", "configuration is null")]),
        ("ICP", "inceptive", [("k", "overt", "configuration overt"), ("g", "conditioned_allomorph", "configuration is null")]),
        ("ATV", "attenuative", [("p", "overt", "configuration overt"), ("b", "conditioned_allomorph", "configuration is null")]),
        ("GRA", "graduative", [("g", "overt", "configuration overt"), ("gz", "conditioned_allomorph", "configuration is null")]),
        ("DPL", "depletive", [("b", "overt", "configuration overt"), ("bz", "conditioned_allomorph", "configuration is null")]),
    ]
    for code, name, variants in extensions:
        group = stable_id("AG", "extension", code)
        for form, realization, condition in variants:
            b.add_atomic(
                surface=form,
                family="extension",
                morpheme_class="CA_consonantal_exponent",
                slot="VI / C_A complex",
                category_code="EXTENSION",
                category_name="Extension",
                value_code=code,
                value_name=name,
                semantic_summary=f"Extension value {name}",
                realization_type=realization,
                allomorph_condition=condition,
                allomorph_group=group,
                locator=ca_locator,
            )

    perspective_essence = [
        ("M.NRM", "monadic + normal", [("∅", "zero", "default/unmarked"), ("l", "standalone_allomorph", "sole exponent in C_A complex")]),
        ("M.RPV", "monadic + representative", [("l", "overt", "inside C_A complex"), ("tļ", "standalone_allomorph", "sole exponent in C_A complex")]),
        ("G.NRM", "agglomerative + normal", [("r", "overt", "")]),
        ("G.RPV", "agglomerative + representative", [("ř", "overt", "")]),
        ("N.NRM", "nomic + normal", [("w", "overt", "inside C_A complex"), ("v", "standalone_allomorph", "sole exponent in C_A complex")]),
        ("N.RPV", "nomic + representative", [("m", "overt", "default; use h when immediately preceded by consonant+t, consonant+p, or consonant+k"), ("h", "conditioned_allomorph", "immediately preceded by consonant+t, consonant+p, or consonant+k")]),
        ("A.NRM", "abstract + normal", [("y", "overt", "inside C_A complex"), ("j", "standalone_allomorph", "sole exponent in C_A complex")]),
        ("A.RPV", "abstract + representative", [("n", "overt", "default; use ç when immediately preceded by consonant+t, consonant+p, or consonant+k"), ("ç", "conditioned_allomorph", "immediately preceded by consonant+t, consonant+p, or consonant+k")]),
    ]
    for code, name, variants in perspective_essence:
        group = stable_id("AG", "perspective_essence", code)
        for form, realization, condition in variants:
            b.add_atomic(
                surface=form,
                family="perspective_essence",
                morpheme_class="CA_fused_exponent",
                slot="VI / C_A complex",
                category_code="PERSPECTIVE_ESSENCE",
                category_name="Perspective + Essence",
                value_code=code,
                value_name=name,
                semantic_summary=f"Fused perspective and essence value {name}",
                realization_type=realization,
                allomorph_condition=condition,
                allomorph_group=group,
                locator=ca_locator,
            )

    b.add_composition(
        composition_type="morpheme_complex_template",
        construction_name="C_A affix-complex",
        surface_pattern="AFFILIATION + CONFIGURATION + EXTENSION + PERSPECTIVE/ESSENCE",
        slot="VI",
        category_code="CA_COMPLEX",
        category_name="C_A complex",
        value_code="CA",
        value_name="C_A",
        semantic_summary="C_A combines affiliation, configuration, extension, perspective, and essence morphology.",
        derivation="source_template",
        locator=ca_locator,
        components=[
            {"role": "category", "literal": "AFFILIATION", "slot": "VI"},
            {"role": "category", "literal": "CONFIGURATION", "slot": "VI"},
            {"role": "category", "literal": "EXTENSION", "slot": "VI"},
            {"role": "fused category", "literal": "PERSPECTIVE/ESSENCE", "slot": "VI"},
        ],
    )

    substitutions = [
        ("pp", "", "mp"),
        ("pb", "", "mb"),
        ("rr", "", "ns"),
        ("[C]gm", "", "[C]x"),
        ("[C]bm", "", "[C]v"),
        ("tt", "", "nt"),
        ("kg", "", "ng"),
        ("rř", "", "nš"),
        ("[C]gn", "", "[C]ň"),
        ("[C]bn", "", "[C]ḑ"),
        ("kk", "", "nk"),
        ("çy", "", "nd"),
        ("řr", "", "ňs"),
        ("ngn", "", "ňn"),
        ("fbm", "fv", "vw"),
        ("ll", "", "pļ"),
        ("řř", "", "ňš"),
        ("[C]çx", "", "[C]xw"),
        ("ţbn", "tḑ", "ḑy"),
    ]
    for input_pattern, intermediate, output_pattern in substitutions:
        b.add_allomorph_rule(
            domain="C_A affix-complex",
            input_pattern=input_pattern,
            intermediate_pattern=intermediate,
            output_pattern=output_pattern,
            condition_summary="Apply when concatenated C_A exponents produce the listed input cluster.",
            locator=ca_locator,
        )


def extract_slot_iv_vr(b: Builder) -> None:
    """Extract the complete Function × Specification × Context Slot-IV matrix."""
    rows = b.table_rows("NI-WEB-CH03", 40)
    locator = b.locator_for_table("NI-WEB-CH03", 40)
    contexts = [value.replace("*", "").strip() for value in rows[1]]
    function = ""
    value_count = 0
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
        if not function or len(forms) != 4:
            continue
        for context, form in zip(contexts, forms):
            add_variants(
                b,
                form=form,
                family="function_specification_context",
                morpheme_class="VR_vocalic_exponent",
                slot="IV / V_R",
                locator=locator,
                category_code="FUNCTION_SPECIFICATION_CONTEXT",
                category_name="Function × Specification × Context",
                value_code=f"{function}.{specification}.{context}",
                value_name=f"{function} {specification} {context}",
                semantic_summary=f"Slot-IV V_R exponent for {function} function, {specification} specification, {context} context",
            )
            value_count += 1
    if value_count != 32:
        raise RuntimeError(f"expected 32 Slot-IV V_R values, found {value_count}")


def extract_cases(b: Builder) -> list[dict[str, object]]:
    case_rows: list[dict[str, object]] = []
    ch4_case_loci: dict[str, dict[str, str]] = {}
    for table_index, table in enumerate(b.tree("NI-WEB-CH04").xpath("//table"), start=1):
        rows = table_matrix(table)
        if len(rows) != 1 or len(rows[0]) < 3 or not re.fullmatch(r"[A-Z]{3}", rows[0][1]):
            continue
        code = rows[0][1]
        current = table.getnext()
        declaration_line = int(table.sourceline or 0)
        while current is not None and current.tag != "table":
            if current.tag == "p":
                text = clean(" ".join(current.itertext()))
                if "case is marked by" in text.lower():
                    declaration_line = int(current.sourceline or declaration_line)
                    break
            current = current.getnext()
        section = b.section_for_line("NI-WEB-CH04", declaration_line)
        ch4_case_loci[code] = {
            "source_id": "NI-WEB-CH04",
            "section_id": section["section_id"] if section else "",
            "table_id": f"NI-WEB-CH04:T{table_index:03d}",
            "source_line": str(declaration_line),
            "source_url": b.source_by_id["NI-WEB-CH04"]["final_url"],
            "source_anchor": section["source_anchor"] if section else "",
        }

    case_tables = range(11, 19)
    case_index = 0
    for table_index in case_tables:
        locator = b.locator_for_table("NI-WEB-CH07", table_index)
        rows = b.table_rows("NI-WEB-CH07", table_index)
        for row in rows[1:]:
            if len(row) < 3 or not row[0].isdigit():
                continue
            case_index = int(row[0])
            label_parts = clean(row[1]).split(maxsplit=1)
            code = label_parts[0].upper()
            name = label_parts[1] if len(label_parts) > 1 else code
            vx_form = row[2]
            description = row[3] if len(row) > 3 else ""
            role_match = re.search(r"Semantic role:\s*([A-Z+ /-]+)", description)
            role = clean(role_match.group(1)) if role_match else ""

            # V_X is independently attested in the Chapter 7 case-accessor table.
            vx_ids = add_variants(
                b,
                form=vx_form,
                family="case_accessor_vowel",
                morpheme_class="VX_vocalic_exponent",
                slot="V/VII or affixual adjunct",
                locator=locator,
                category_code="CASE_ACCESSOR_VX",
                category_name="Case-derived V_X",
                value_code=code,
                value_name=name,
                semantic_summary=f"V_X value corresponding to {name} case",
            )

            # Chapter 4 is the source of the actual V_C case exponent.  Cases
            # 1-36 use the same base sequence, while 37-68 add the glottal marker.
            ch4_loc = ch4_case_loci.get(code)
            if not ch4_loc:
                raise RuntimeError(f"missing Chapter 4 source locus for case {code}")
            source_variants = surface_variants(vx_form)
            if case_index >= 37:
                source_variants = [source_variants[0]]
            case_group = stable_id("AG", "case", code)
            case_atomic_ids: list[str] = []
            for surface, realization, condition in source_variants:
                if case_index >= 37:
                    normalized_surface = strip_bound_form(surface)
                    underlying = f"{normalized_surface}’"
                    realized = glottal_realization(normalized_surface)
                    case_atomic_ids.append(
                        b.add_atomic(
                            surface=underlying,
                            family="case",
                            morpheme_class="VC_vocalic_exponent",
                            slot="IX",
                            category_code="CASE",
                            category_name="Case",
                            value_code=code,
                            value_name=name,
                            semantic_summary=f"{name} case" + (f"; semantic role {role}" if role else ""),
                            realization_type="underlying_glottal",
                            allomorph_condition="formative Slot IX underlying case form",
                            allomorph_group=case_group,
                            derivation="source_rule_plus_table",
                            locator=ch4_loc,
                        )
                    )
                    case_atomic_ids.append(
                        b.add_atomic(
                            surface=realized,
                            family="case",
                            morpheme_class="VC_vocalic_exponent",
                            slot="IX",
                            category_code="CASE",
                            category_name="Case",
                            value_code=code,
                            value_name=name,
                            semantic_summary=f"{name} case realized glottal form",
                            realization_type="realized_allomorph",
                            allomorph_condition="surface realization of glottal case form",
                            allomorph_group=case_group,
                            derivation="source_rule_plus_table",
                            locator=ch4_loc,
                        )
                    )
                else:
                    case_atomic_ids.append(
                        b.add_atomic(
                            surface=surface,
                            family="case",
                            morpheme_class="VC_vocalic_exponent",
                            slot="IX",
                            category_code="CASE",
                            category_name="Case",
                            value_code=code,
                            value_name=name,
                            semantic_summary=f"{name} case" + (f"; semantic role {role}" if role else ""),
                            realization_type=realization,
                            allomorph_condition=condition,
                            allomorph_group=case_group,
                            derivation="source_rule_plus_table",
                            locator=ch4_loc,
                        )
                    )
            for atomic_id in case_atomic_ids:
                b.add_assertion("atomic_morpheme", atomic_id, "case_table_crosscheck", locator)
            case_rows.append(
                {
                    "index": case_index,
                    "code": code,
                    "name": name,
                    "vx_form": vx_form,
                    "vx_ids": vx_ids,
                    "vc_ids": case_atomic_ids,
                    "locator": locator,
                }
            )
    if case_index != 68 or len(case_rows) != 68:
        raise RuntimeError(f"expected 68 cases, found {len(case_rows)} ending at {case_index}")
    return case_rows


def glottal_realization(vowel: str) -> str:
    vowel = normalize_form(vowel)
    if len(vowel) == 1:
        return f"{vowel}’{vowel}"
    return f"{vowel[0]}’{vowel[1:]}"


def extract_case_scope(b: Builder) -> None:
    rows = b.table_rows("NI-WEB-CH04", 102)
    locator = b.locator_for_table("NI-WEB-CH04", 102)
    for row in rows[1:]:
        if len(row) < 4:
            continue
        code, name, pattern1, pattern2 = row[:4]
        for pattern_name, form in (("Pattern 1", pattern1), ("Pattern 2", pattern2)):
            add_variants(
                b,
                form=form,
                family="case_scope",
                morpheme_class="CN_consonantal_exponent",
                slot="VIII",
                locator=locator,
                category_code="CASE_SCOPE",
                category_name="Case-Scope",
                value_code=f"{code}.{pattern_name.replace(' ', '').upper()}",
                value_name=f"{name} {pattern_name}",
                semantic_summary=f"{name} case-scope, {pattern_name}",
            )


def extract_ch5(b: Builder) -> None:
    locator = b.locator_for_table("NI-WEB-CH05", 3)
    rows = b.table_rows("NI-WEB-CH05", 3)
    for row in rows[2:]:
        if len(row) < 12:
            continue
        groups = [
            ("valence", "Valence", "VIII / V_N", row[1], row[1], row[2]),
            ("phase", "Phase", "VIII / V_N", row[4], row[4], row[5]),
            ("effect", "Effect", "VIII / V_N", row[7], row[7], row[8]),
            ("level", "Level", "VIII / V_N", row[10], row[10], row[11]),
        ]
        for family, category_name, slot, code, name, form in groups:
            add_variants(
                b,
                form=form,
                family=family,
                morpheme_class="VN_vocalic_exponent",
                slot=slot,
                locator=locator,
                category_code=family.upper(),
                category_name=category_name,
                value_code=code,
                value_name=name,
                semantic_summary=f"{category_name} value {name}",
            )

    mood_values = [
        ("FAC", "factual", "h", "default/unmarked if Slot VIII otherwise empty"),
        ("SUB", "subjunctive", "hl", ""),
        ("ASM", "assumptive", "hr", ""),
        ("SPC", "speculative", "hm", ""),
        ("COU", "counterfactive", "hn", ""),
        ("HYP", "hypothetical", "hň", ""),
    ]
    for code, name, form, condition in mood_values:
        b.add_atomic(
            surface=form,
            family="mood",
            morpheme_class="CN_consonantal_exponent",
            slot="VIII",
            category_code="MOOD",
            category_name="Mood",
            value_code=code,
            value_name=name,
            semantic_summary=f"{name} mood",
            realization_type="overt_optional" if code == "FAC" else "overt",
            allomorph_condition=condition,
            locator=locator,
        )

    aspect_locator = b.locator_for_table("NI-WEB-CH05", 4)
    rows = b.table_rows("NI-WEB-CH05", 4)
    aspect_count = 0
    for row in rows[1:]:
        for offset in (0, 4, 8, 12):
            if len(row) < offset + 3:
                continue
            code, name, form = row[offset : offset + 3]
            if not code or not name or not form:
                continue
            add_variants(
                b,
                form=form,
                family="aspect",
                morpheme_class="VN_vocalic_exponent",
                slot="VIII",
                locator=aspect_locator,
                category_code="ASPECT",
                category_name="Aspect",
                value_code=code,
                value_name=name,
                semantic_summary=f"Aspect value {name}",
            )
            aspect_count += 1
    if aspect_count != 36:
        raise RuntimeError(f"expected 36 aspect values, found {aspect_count}")

    # Explicit Slot VIII templates preserve linguistic component order.
    b.add_composition(
        composition_type="slot_template",
        construction_name="Slot VIII Pattern 1",
        surface_pattern="V_N + C_N",
        slot="VIII",
        category_code="SLOT_VIII_PATTERN_1",
        category_name="Slot VIII",
        value_code="VN_CN",
        value_name="Valence/Phase/Effect/Level + Mood/Case-Scope",
        semantic_summary="Pattern 1 combines one V_N category value with a following C_N mood or case-scope value.",
        derivation="source_template",
        locator=locator,
        components=[
            {"role": "vocalic category exponent", "literal": "V_N", "slot": "VIII"},
            {"role": "consonantal mood/case-scope exponent", "literal": "C_N", "slot": "VIII"},
        ],
    )
    b.add_composition(
        composition_type="slot_template",
        construction_name="Slot VIII Pattern 2",
        surface_pattern="ASPECT V_N + C_N",
        slot="VIII",
        category_code="SLOT_VIII_PATTERN_2",
        category_name="Slot VIII",
        value_code="ASPECT_CN",
        value_name="Aspect + Mood/Case-Scope",
        semantic_summary="Pattern 2 combines an aspect V_N exponent with a following C_N mood or case-scope value.",
        derivation="source_template",
        locator=aspect_locator,
        components=[
            {"role": "aspect exponent", "literal": "V_N", "slot": "VIII"},
            {"role": "consonantal mood/case-scope exponent", "literal": "C_N", "slot": "VIII"},
        ],
    )


def extract_ch6(b: Builder) -> None:
    rows = b.table_rows("NI-WEB-CH06", 4)
    locator = b.locator_for_table("NI-WEB-CH06", 4)
    for row_index, row in enumerate(rows[1:], start=2):
        if len(row) < 2:
            continue
        if row_index == 2 and len(row) >= 5:
            illocution = row[0].split(maxsplit=1)
            validation_code = row[1]
            form = row[-1]
            if illocution:
                b.add_atomic(
                    surface=strip_bound_form(form.strip("()")),
                    family="illocution",
                    morpheme_class="VK_vocalic_exponent",
                    slot="IX",
                    category_code="ILLOCUTION",
                    category_name="Illocution",
                    value_code=illocution[0],
                    value_name=illocution[1] if len(illocution) > 1 else illocution[0],
                    semantic_summary="assertive illocution",
                    realization_type="overt_optional",
                    allomorph_condition="default/shared V_K value",
                    locator=locator,
                )
            b.add_atomic(
                surface=strip_bound_form(form.strip("()")),
                family="validation",
                morpheme_class="VK_vocalic_exponent",
                slot="IX",
                category_code="VALIDATION",
                category_name="Validation",
                value_code=validation_code,
                value_name="observational",
                semantic_summary="observational validation",
                realization_type="overt_optional",
                allomorph_condition="default/shared V_K value",
                locator=locator,
            )
            continue
        if row_index <= 10 and len(row) >= 4:
            code, name, form = row[0], row[1], row[-1]
            b.add_atomic(
                surface=strip_bound_form(form),
                family="validation",
                morpheme_class="VK_vocalic_exponent",
                slot="IX",
                category_code="VALIDATION",
                category_name="Validation",
                value_code=code.replace(" ", ""),
                value_name=name,
                semantic_summary=f"{name} validation",
                locator=locator,
            )
        elif len(row) >= 3:
            code, name, form = row[0], row[1], row[-1]
            if not code or not name or not form:
                continue
            b.add_atomic(
                surface=strip_bound_form(form),
                family="illocution",
                morpheme_class="VK_vocalic_exponent",
                slot="IX",
                category_code="ILLOCUTION",
                category_name="Illocution",
                value_code=code,
                value_name=name,
                semantic_summary=f"{name} illocution",
                locator=locator,
            )


def extract_vx_degree_matrix(b: Builder) -> None:
    rows = b.table_rows("NI-WEB-CH07", 3)
    locator = b.locator_for_table("NI-WEB-CH07", 3)
    for row in rows[1:]:
        if len(row) < 5 or not row[1].isdigit():
            continue
        degree = int(row[1])
        for type_number, form in enumerate(row[2:5], start=1):
            ids = add_variants(
                b,
                form=form,
                family="affix_vowel",
                morpheme_class="VX_vocalic_exponent",
                slot="V/VII or affixual adjunct",
                locator=locator,
                category_code=f"VX_TYPE_{type_number}",
                category_name=f"V_X affix type {type_number}",
                value_code=f"T{type_number}.D{degree}",
                value_name=f"Type {type_number} degree {degree}",
                semantic_summary=f"V_X exponent for affix type {type_number}, degree {degree}",
            )
            b.vx_by_degree_type[(degree, type_number)].extend(ids)


FORM_CODE_RE = re.compile(r"^([A-Z0-9]{2,7}\*?)\s+(.+)$")


def bound_forms(value: str) -> list[str]:
    value = clean(value)
    if not value.startswith("-") or len(value) > 60:
        return []
    forms = [clean(match) for match in re.findall(r"-\s*([^\s/’‘\"(),;]+)", value)]
    out: list[str] = []
    for form in forms:
        normalized = normalize_form(form)
        if not normalized or normalized.upper() in {"V", "VX", "VC", "VK", "VN", "CS", "CA", "CR", "CN"}:
            continue
        if len(normalized) <= 12:
            out.append(form)
    return out


def extract_affix_roots_and_degrees(b: Builder) -> None:
    allowed_sources = ["NI-WEB-CH04", "NI-WEB-CH05", "NI-WEB-CH07", "NI-WEB-CH13", "NI-WEB-APP"]
    excluded = {("NI-WEB-CH13", 2), ("NI-WEB-CH13", 3), ("NI-WEB-CH08", 10)}
    for source_id in allowed_sources:
        for table_index, table in enumerate(b.tree(source_id).xpath("//table"), start=1):
            if (source_id, table_index) in excluded:
                continue
            rows = table_matrix(table)
            if not rows:
                continue
            locator = b.locator_for_table(source_id, table_index)
            header_pairs: list[tuple[int, str, str, str]] = []
            first = rows[0]
            for col in range(len(first) - 1):
                forms = bound_forms(first[col])
                label_match = FORM_CODE_RE.match(clean(first[col + 1]))
                if not forms or not label_match:
                    continue
                code = label_match.group(1).rstrip("*")
                name = label_match.group(2)
                for form in forms:
                    atomic_id = b.add_atomic(
                        surface=form,
                        family="affix_root",
                        morpheme_class="CS_consonantal_root",
                        slot="V/VII or affixual adjunct",
                        category_code="VXCS_AFFIX_ROOT",
                        category_name="V_XC_S affix root",
                        value_code=code,
                        value_name=name,
                        semantic_summary=name,
                        locator=locator,
                    )
                    b.affix_roots[atomic_id] = {"code": code, "name": name, "locator": locator}
                    header_pairs.append((col, atomic_id, code, name))
            for col, atomic_id, code, name in header_pairs:
                for row in rows[1:]:
                    if len(row) <= col + 1:
                        continue
                    degree_text = clean(row[col])
                    if not degree_text.isdigit() or int(degree_text) not in range(10):
                        continue
                    b.add_affix_degree(atomic_id, int(degree_text), row[col + 1], locator)

            # Tables such as Chapter 13 T8 list one form+code pair per row rather
            # than a header followed by a degree spectrum.
            for row in rows:
                for col in range(len(row) - 1):
                    forms = bound_forms(row[col])
                    label_match = FORM_CODE_RE.match(clean(row[col + 1]))
                    if not forms or not label_match:
                        continue
                    code = label_match.group(1).rstrip("*")
                    name = label_match.group(2)
                    for form in forms:
                        atomic_id = b.add_atomic(
                            surface=form,
                            family="affix_root",
                            morpheme_class="CS_consonantal_root",
                            slot="V/VII or affixual adjunct",
                            category_code="VXCS_AFFIX_ROOT",
                            category_name="V_XC_S affix root",
                            value_code=code,
                            value_name=name,
                            semantic_summary=name,
                            locator=locator,
                        )
                        b.affix_roots[atomic_id] = {"code": code, "name": name, "locator": locator}


def generate_vxcs_compositions(b: Builder) -> None:
    # Only roots with source-provided degree semantics are expanded.  This
    # prevents inventing degree meanings for fixed-form or non-gradient roots.
    degrees_by_root: dict[str, set[int]] = defaultdict(set)
    meanings: dict[tuple[str, int], str] = {}
    for row in b.affix_degrees.values():
        root = row["affix_root_atomic_id"]
        degree = int(row["degree"])
        degrees_by_root[root].add(degree)
        meanings[(root, degree)] = row["meaning_summary"]

    template_loc = b.locator_for_table("NI-WEB-CH07", 3)
    for root_id, degrees in sorted(degrees_by_root.items()):
        root = b.atomic[root_id]
        for degree in sorted(degrees):
            for type_number in (1, 2, 3):
                for vx_id in b.vx_by_degree_type.get((degree, type_number), []):
                    vx = b.atomic[vx_id]
                    if vx["realization_type"] == "conditioned_allomorph":
                        condition = vx["allomorph_condition"]
                    else:
                        condition = vx["allomorph_condition"]
                    surface = f"{vx['surface_form_raw']}{root['surface_form_raw']}"
                    comp_id = b.add_composition(
                        composition_type="VXCS_affix",
                        construction_name="V_XC_S affix",
                        surface=surface,
                        surface_pattern="V_X + C_S",
                        slot="VII / standard orientation",
                        category_code="VXCS",
                        category_name="V_XC_S affix",
                        value_code=f"{root['value_code']}/T{type_number}/D{degree}",
                        value_name=f"{root['value_name']} type {type_number} degree {degree}",
                        semantic_summary=f"{root['value_name']}; degree {degree}: {meanings[(root_id, degree)]}",
                        condition=condition,
                        derivation="source_join",
                        locator=root_source_locator(root),
                        components=[
                            {"role": "type/degree vowel", "atomic_id": vx_id, "slot": "V_X", "condition": condition},
                            {"role": "affix root", "atomic_id": root_id, "slot": "C_S"},
                        ],
                        assertion_kind="root_degree_join",
                    )
                    b.add_assertion("morpheme_composition", comp_id, "vx_matrix_join", template_loc)


def root_source_locator(row: dict[str, str]) -> dict[str, str]:
    return {
        "source_id": row["primary_source_id"],
        "section_id": row["primary_section_id"],
        "table_id": row["primary_table_id"],
        "source_line": row["primary_source_line"],
        "source_url": row["primary_source_url"],
        "source_anchor": row["primary_source_anchor"],
    }


def generate_case_affix_compositions(b: Builder, cases: list[dict[str, object]]) -> None:
    locator = b.locator_for_table("NI-WEB-CH07", 19)
    roles = [
        ("case_accessor", 1, "sw", "sy"),
        ("case_accessor", 2, "zw", "zy"),
        ("case_accessor", 3, "čw", "čy"),
        ("inverse_case_accessor", 1, "šw", "šy"),
        ("inverse_case_accessor", 2, "žw", "žy"),
        ("inverse_case_accessor", 3, "jw", "jy"),
        ("case_stacking", 1, "lw", "ly"),
    ]
    cs_atoms: dict[tuple[str, int, str], str] = {}
    for role, type_number, low_form, high_form in roles:
        for range_name, form in (("cases_1_36", low_form), ("cases_37_68", high_form)):
            code = f"{role.upper()}.T{type_number}.{range_name.upper()}"
            cs_atoms[(role, type_number, range_name)] = b.add_atomic(
                surface=form,
                family="case_affix_root",
                morpheme_class="CS_consonantal_root",
                slot="V/VII or affixual adjunct",
                category_code=role.upper(),
                category_name=role.replace("_", " ").title(),
                value_code=code,
                value_name=f"{role.replace('_',' ')} type {type_number}, {range_name.replace('_',' ')}",
                semantic_summary=f"Consonantal increment used for {role.replace('_',' ')} type {type_number}",
                locator=locator,
            )

    for case in cases:
        case_number = int(case["index"])
        range_name = "cases_1_36" if case_number <= 36 else "cases_37_68"
        for role, type_number, _low, _high in roles:
            cs_id = cs_atoms[(role, type_number, range_name)]
            for vx_id in case["vx_ids"]:  # type: ignore[index]
                vx = b.atomic[vx_id]
                cs = b.atomic[cs_id]
                surface = f"{vx['surface_form_raw']}{cs['surface_form_raw']}"
                comp_id = b.add_composition(
                    composition_type=role,
                    construction_name=role.replace("_", " ").title(),
                    surface=surface,
                    surface_pattern="V_X + C_S",
                    slot="V/VII or affixual adjunct",
                    category_code=role.upper(),
                    category_name=role.replace("_", " ").title(),
                    value_code=f"{case['code']}.T{type_number}",
                    value_name=f"{case['name']} {role.replace('_',' ')} type {type_number}",
                    semantic_summary=f"{role.replace('_',' ').title()} derived from {case['name']} case",
                    condition=vx["allomorph_condition"],
                    derivation="source_join",
                    locator=case["locator"],  # type: ignore[arg-type]
                    components=[
                        {"role": "case-derived vowel", "atomic_id": vx_id, "slot": "V_X", "condition": vx["allomorph_condition"]},
                        {"role": "accessor/stacking root", "atomic_id": cs_id, "slot": "C_S"},
                    ],
                    assertion_kind="case_vx_join",
                )
                b.add_assertion("morpheme_composition", comp_id, "case_affix_cs_join", locator)


def extract_register_and_suppletive_adjuncts(b: Builder, cases: list[dict[str, object]]) -> None:
    register_locator = b.locator_for_table("NI-WEB-CH08", 5)
    rows = b.table_rows("NI-WEB-CH08", 5)
    register_count = 0
    for row in rows[1:]:
        if len(row) < 4 or not re.fullmatch(r"[A-Z]{3}", row[0]):
            continue
        code, name, initial, final = row[:4]
        name = re.sub(r"\s+[12]$", "", clean(name))
        for position, form in (("initial", initial), ("final", final)):
            if code == "END" and position == "initial" and form in {"—", "-", ""}:
                continue
            if form in {"—", "-", ""}:
                surface = "∅"
                realization = "zero"
                condition = "unmarked/default register boundary"
            else:
                parenthetical = re.fullmatch(r"\(([^)]+)\)", clean(form))
                surface = strip_bound_form(parenthetical.group(1) if parenthetical else form)
                realization = "overt_optional" if position == "final" else "overt"
                condition = (
                    "final register adjunct; may be omitted when the last word of the register clause is pronounced with low pitch where the source permits"
                    if position == "final"
                    else "placed at the start of the registered word or phrase"
                )
            if code == "SPF" and position == "initial":
                condition += "; preceding referent is a proper name, otherwise use PNT register"
            if code == "END" and position == "final":
                condition += "; use as the carrier-end marker where a register contains a proper name or foreign word/phrase"
            b.add_atomic(
                surface=surface,
                family=f"register_adjunct_{position}",
                morpheme_class="fixed_register_adjunct",
                slot=f"register {position}",
                category_code="REGISTER",
                category_name="Register",
                value_code=code,
                value_name=name,
                semantic_summary=f"{name} register {position} adjunct",
                realization_type=realization,
                allomorph_condition=condition,
                locator=register_locator,
            )
            register_count += 1
    if register_count != 13:
        raise RuntimeError(f"expected 13 initial/final register records, found {register_count}")

    suppletive_specs = [
        (6, "CAR", "Carrier Adjunct", "hl"),
        (7, "QUO", "Quotative Adjunct", "hm"),
        (8, "NAM", "Naming Adjunct", "hn"),
        (9, "PHR", "Phrasal Adjunct", "hň"),
    ]
    cp_atoms: dict[str, str] = {}
    for table_index, code, name, expected_form in suppletive_specs:
        locator = b.locator_for_table("NI-WEB-CH08", table_index)
        rows = b.table_rows("NI-WEB-CH08", table_index)
        form = strip_bound_form(rows[1][0]) if len(rows) > 1 and rows[1] else ""
        if form != expected_form:
            raise RuntimeError(f"unexpected {code} C_P form {form!r}, expected {expected_form!r}")
        cp_atoms[code] = b.add_atomic(
            surface=form,
            family="suppletive_adjunct_cp",
            morpheme_class="CP_consonantal_exponent",
            slot="suppletive adjunct C_P",
            category_code="SUPPLETIVE_ADJUNCT",
            category_name="Suppletive adjunct",
            value_code=code,
            value_name=name,
            semantic_summary=f"{name} fixed C_P exponent",
            locator=locator,
        )

        for case in cases:
            case_number = int(case["index"])
            case_surfaces = [b.atomic[vc_id] for vc_id in case["vc_ids"]]  # type: ignore[index]
            if case_number <= 36:
                applicable = [
                    vc
                    for vc in case_surfaces
                    if vc["realization_type"] not in {"conditioned_allomorph", "underlying_glottal"}
                ]
                join_condition = "default V_C surface after fixed C_P; y/w-conditioned alternants do not apply"
            else:
                applicable = [vc for vc in case_surfaces if vc["realization_type"] == "realized_allomorph"]
                join_condition = "required realized word-final glottal V_C surface"
            if len(applicable) != 1:
                raise RuntimeError(
                    f"expected one applicable V_C surface for {code}.{case['code']}, found "
                    f"{[(vc['surface_form_raw'], vc['realization_type']) for vc in applicable]}"
                )
            vc = applicable[0]
            vc_id = vc["atomic_id"]
            surface = f"{form}{vc['surface_form_raw']}"
            comp_id = b.add_composition(
                composition_type="suppletive_adjunct",
                construction_name=name,
                surface=surface,
                surface_pattern="C_P + V_C",
                slot="suppletive adjunct",
                category_code="SUPPLETIVE_ADJUNCT",
                category_name="Suppletive adjunct",
                value_code=f"{code}.{case['code']}",
                value_name=f"{name} with {case['name']} case",
                semantic_summary=f"{name} carrying the formative Slot-IX V_C value for {case['name']} case",
                condition=join_condition,
                derivation="source_join",
                locator=locator,
                components=[
                    {"role": "suppletive adjunct marker", "atomic_id": cp_atoms[code], "slot": "C_P"},
                    {"role": "case exponent", "atomic_id": vc_id, "slot": "V_C", "condition": join_condition},
                ],
                assertion_kind="suppletive_cp_vc_join",
            )
            b.add_assertion("morpheme_composition", comp_id, "case_vc_component", root_source_locator(vc))


def extract_bias_adjuncts(b: Builder) -> None:
    rows = b.table_rows("NI-WEB-CH08", 10)
    locator = b.locator_for_table("NI-WEB-CH08", 10)
    count = 0
    for row in rows:
        if len(row) < 3 or not re.fullmatch(r"[A-Z]{3}", row[0]):
            continue
        code, name, form = row[:3]
        b.add_atomic(
            surface=form,
            family="bias_adjunct",
            morpheme_class="fixed_consonantal_adjunct",
            slot="adjunct",
            category_code="BIAS",
            category_name="Bias adjunct",
            value_code=code,
            value_name=name,
            semantic_summary=f"{name} bias adjunct",
            locator=locator,
        )
        count += 1
    if count != 61:
        raise RuntimeError(f"expected 61 bias adjuncts, found {count}")


def extract_referentials(b: Builder) -> None:
    rows = b.table_rows("NI-WEB-CH09", 3)
    locator = b.locator_for_table("NI-WEB-CH09", 3)
    effects = ["neutral", "beneficial", "detrimental"]
    count = 0
    for row in rows[2:]:
        if len(row) < 5:
            continue
        code, name = row[0], row[1]
        for effect_index, effect in enumerate(effects, start=2):
            if effect_index >= len(row):
                continue
            form = row[effect_index]
            add_variants(
                b,
                form=form,
                family="referential",
                morpheme_class="referential_consonantal_exponent",
                slot="referential C1/C2",
                locator=locator,
                category_code="REFERENTIAL",
                category_name="Personal referent",
                value_code=f"{code}.{effect.upper()}",
                value_name=f"{name}, {effect} effect",
                semantic_summary=f"Referent {name} with {effect} effect",
                alternate_condition=(
                    "Referential Affixes only; used to avoid ambiguity with geminated C_A forms"
                    if "*" in form
                    else ""
                ),
            )
            count += 1
    if count != 33:
        raise RuntimeError(f"expected 33 referential category/effect cells, found {count}")


def root_header_info(header: str) -> tuple[str, str]:
    match = re.search(r"-\s*([^-]+?)\s*-", clean(header))
    if not match:
        raise RuntimeError(f"cannot parse root header: {header!r}")
    root = re.sub(r"\s+", "", match.group(1)).upper()
    name = clean(header[match.end() :]).strip().strip("‘’\"'")
    return root, short_meaning(name or f"root {root}", 160)


def table_root_atomic(b: Builder, source_id: str, table_index: int) -> tuple[str, str, dict[str, str]]:
    rows = b.table_rows(source_id, table_index)
    root, name = root_header_info(rows[0][0])
    locator = b.locator_for_table(source_id, table_index)
    normalized = normalize_form(root)
    existing = next(
        (
            atomic_id
            for atomic_id, row in b.atomic.items()
            if row["morpheme_class"] == "lexical_consonantal_root" and row["surface_form_normalized"] == normalized
        ),
        None,
    )
    if existing:
        b.add_assertion("atomic_morpheme", existing, "root_paradigm", locator)
        return existing, root, locator
    atomic_id = b.add_atomic(
        surface=root,
        family="lexical_root",
        morpheme_class="lexical_consonantal_root",
        slot="III / C_R",
        category_code="LEXICAL_ROOT",
        category_name="Lexical root",
        value_code=f"ROOT.{root}",
        value_name=name,
        semantic_summary=name,
        locator=locator,
        assertion_kind="root_paradigm",
    )
    return atomic_id, root, locator


def extract_regular_root_paradigm(b: Builder, source_id: str, table_index: int) -> None:
    """Parse tables with explicit Stem 1/2/3 columns and BSC/CTE/CSV/OBJ rows."""
    rows = b.table_rows(source_id, table_index)
    atomic_id, _root, locator = table_root_atomic(b, source_id, table_index)
    if len(rows) < 3 or len(rows[1]) < 4:
        raise RuntimeError(f"root paradigm {source_id}:T{table_index:03d} lacks three stem columns")
    stems = [clean(value) for value in rows[1][1:4]]
    added = 0
    for row in rows[2:]:
        if len(row) < 4 or row[0] not in {"BSC", "CTE", "CSV", "OBJ"}:
            continue
        for stem, summary in zip(stems, row[1:4]):
            if summary:
                b.add_root_sense(atomic_id, stem, row[0], summary, locator)
                added += 1
    if added != 12:
        raise RuntimeError(f"expected 12 root senses at {source_id}:T{table_index:03d}, found {added}")


def extract_compact_root_paradigm(b: Builder, source_id: str, table_index: int) -> None:
    """Parse compact root tables whose Stem 2/3 definitions share a cell."""
    rows = b.table_rows(source_id, table_index)
    atomic_id, _root, locator = table_root_atomic(b, source_id, table_index)
    combined = " ".join(cell for row in rows[:2] for cell in row)
    stem2 = re.search(r"Stem\s*2\s*:\s*(.*?)(?=\s+Stem\s*3\s*:|$)", combined, flags=re.I)
    stem3 = re.search(r"Stem\s*3\s*:\s*(.*)$", combined, flags=re.I)
    if stem2:
        b.add_root_sense(atomic_id, "Stem 2", "BSC", stem2.group(1), locator)
    if stem3:
        b.add_root_sense(atomic_id, "Stem 3", "BSC", stem3.group(1), locator)

    stem1_specs = 0
    for row in rows[1:]:
        if len(row) < 2 or row[0] not in {"BSC", "CTE", "CSV", "OBJ"}:
            continue
        summary = re.sub(r"^Stem\s*1\s*:\s*", "", row[1], flags=re.I)
        if summary:
            b.add_root_sense(atomic_id, "Stem 1", row[0], summary, locator)
            stem1_specs += 1
    if stem1_specs != 4 or not stem2 or not stem3:
        raise RuntimeError(
            f"compact root paradigm {source_id}:T{table_index:03d} expected 4 Stem-1 specs plus Stem 2/3; "
            f"got stem1={stem1_specs} stem2={bool(stem2)} stem3={bool(stem3)}"
        )


def extract_explicit_root_paradigms(b: Builder) -> None:
    for table_index in (7, 8):
        extract_regular_root_paradigm(b, "NI-WEB-CH02", table_index)
    for table_index in (8, 9, 10, 11):
        extract_compact_root_paradigm(b, "NI-WEB-APP", table_index)
    extract_regular_root_paradigm(b, "NI-WEB-CH10", 3)
    for table_index in (11, 12, 13):
        extract_compact_root_paradigm(b, "NI-WEB-CH10", table_index)


def extract_number_roots(b: Builder) -> dict[str, str]:
    locator2 = b.locator_for_table("NI-WEB-CH13", 2)
    roots: dict[str, str] = {}
    rows = b.table_rows("NI-WEB-CH13", 2)
    for number, form in zip(rows[0], rows[1]):
        number = normalize_number_label(number)
        root = strip_bound_form(form).upper()
        atomic_id = b.add_atomic(
            surface=root,
            family="number_root",
            morpheme_class="lexical_consonantal_root",
            slot="III / C_R",
            category_code="NUMBER_ROOT",
            category_name="Number root",
            value_code=f"NUM.{number}",
            value_name=number,
            semantic_summary=f"Number root for {number}",
            locator=locator2,
        )
        roots[root] = atomic_id
    locator3 = b.locator_for_table("NI-WEB-CH13", 3)
    rows = b.table_rows("NI-WEB-CH13", 3)
    for number, form in zip(rows[0], rows[1]):
        number = normalize_number_label(number)
        root = strip_bound_form(form).upper()
        atomic_id = b.add_atomic(
            surface=root,
            family="number_root",
            morpheme_class="lexical_consonantal_root",
            slot="III / C_R",
            category_code="NUMBER_ROOT",
            category_name="Number root",
            value_code=f"NUM.{number}",
            value_name=number,
            semantic_summary=f"Number root for {number}",
            locator=locator3,
        )
        roots[root] = atomic_id

    for table_index in (5, 6, 7):
        locator = b.locator_for_table("NI-WEB-CH13", table_index)
        rows = b.table_rows("NI-WEB-CH13", table_index)
        header = rows[0][0]
        match = re.match(r"-\s*([^\s-]+)\s*-", header)
        if not match:
            continue
        root = match.group(1).upper()
        atomic_id = roots.get(root)
        if not atomic_id:
            continue
        stems = rows[1][1:4]
        for row in rows[2:]:
            if len(row) < 4:
                continue
            specification = row[0]
            for index, summary in enumerate(row[1:4]):
                b.add_root_sense(atomic_id, stems[index], specification, summary, locator)
    return roots


def normalize_number_label(value: str) -> str:
    value = clean(value)
    match = re.fullmatch(r"100\s+([248])", value)
    return f"100^{match.group(1)}" if match else value


def extract_ch10_roots(b: Builder) -> None:
    source_id = "NI-WEB-CH10"
    root_re = re.compile(r"^-\s*([^\s-][^-]{0,16}?)\s*-\s*(.*)$")
    missing_close_re = re.compile(r"^-\s*([^\s-]{1,8})\s+(?=[‘\"])(.*)$")
    count = 0
    for paragraph in b.tree(source_id).xpath("//p"):
        text = clean(" ".join(paragraph.itertext()))
        match = root_re.match(text) or missing_close_re.match(text)
        if not match:
            continue
        root = clean(match.group(1))
        if not root or " " in root and len(root.split()) > 2:
            continue
        rest = match.group(2)
        quoted = re.search(r"[‘\"]([^’\"]+)[’\"]", rest)
        if quoted:
            name = short_meaning(quoted.group(1), 150)
        elif rest.startswith("‘"):
            name = short_meaning(rest.lstrip("‘\"").split(", i.e.", 1)[0], 150)
        elif "carrier" in rest.lower():
            name = "carrier root"
        else:
            continue
        locator = b.locator_for_element(source_id, paragraph)
        atomic_id = b.add_atomic(
            surface=root,
            family="specialized_root",
            morpheme_class="lexical_consonantal_root",
            slot="III / C_R",
            category_code="SPECIALIZED_ROOT",
            category_name="Specialized root",
            value_code=normalize_form(root).upper(),
            value_name=name,
            semantic_summary=name,
            locator=locator,
        )
        b.add_root_sense(atomic_id, "", "", name, locator)
        for stem_number, stem_text in re.findall(r"Stem\s+([123])\s*=\s*([^;\[]+)", rest, flags=re.I):
            b.add_root_sense(atomic_id, f"Stem {stem_number}", "", stem_text, locator)
        count += 1
    if count != 74:
        raise RuntimeError(f"expected 74 Chapter 10 leading roots, found {count}")


def add_source_templates(b: Builder) -> None:
    formative_locator = b.locator_for_table("NI-WEB-CH02", 3)
    b.add_composition(
        composition_type="word_template",
        construction_name="Standard formative",
        surface_pattern="(C_C V_V) + C_R + V_R + (C_S V_X...) + C_A + (V_X C_S...) + (V_N C_N) + V_C/V_K + stress",
        category_code="FORMATIVE",
        category_name="Formative",
        value_code="STANDARD_FORMATIVE",
        value_name="Standard formative slot structure",
        semantic_summary="Ten-slot formative structure with optional concatenation, affix, and modular morphology.",
        derivation="source_template",
        locator=formative_locator,
        components=[
            {"role": "concatenation/version-stem", "literal": "C_C V_V", "slot": "I-II"},
            {"role": "root", "literal": "C_R", "slot": "III"},
            {"role": "function/specification/context", "literal": "V_R", "slot": "IV"},
            {"role": "reversed affixes", "literal": "C_S V_X ...", "slot": "V"},
            {"role": "C_A complex", "literal": "C_A", "slot": "VI"},
            {"role": "standard affixes", "literal": "V_X C_S ...", "slot": "VII"},
            {"role": "modular categories", "literal": "V_N C_N", "slot": "VIII"},
            {"role": "case/illocution-validation", "literal": "V_C / V_K", "slot": "IX"},
            {"role": "relation discriminator", "literal": "stress", "slot": "X"},
        ],
    )

    template_specs = [
        ("NI-WEB-CH08", 2, "single_affix_adjunct", "Single-affix adjunct", "’V_XC_S + V_S + stress"),
        ("NI-WEB-CH08", 3, "multiple_affix_adjunct", "Multiple-affix adjunct", "(ë-)C_SV_X + C_Z + V_XC_S... + V_Z + stress"),
        ("NI-WEB-CH08", 4, "modular_adjunct", "Modular adjunct", "scope marker + (V_NC_N) + (V_NC_M) + V_N/V_H"),
        ("NI-WEB-CH09", 2, "single_referential", "Single referential", "(ë)C_1((ë)C_1((ë)C_1)) + V_C1"),
        ("NI-WEB-CH09", 4, "dual_referential", "Dual-referent referential", "referential A + V_C1 + w/y+V_C2 + referential B + stress"),
        ("NI-WEB-CH10", 4, "specialized_affix_root", "Specialized C_S-root formative", "V_V + C_S-as-root + formative morphology"),
        ("NI-WEB-CH10", 6, "specialized_personal_root", "Specialized personal-reference root", "V_V + personal-reference C_R + formative morphology"),
    ]
    for source_id, table_index, value_code, name, pattern in template_specs:
        locator = b.locator_for_table(source_id, table_index)
        components = [
            {"role": "source-declared template", "literal": part.strip(), "slot": ""}
            for part in re.split(r"\s*\+\s*", pattern)
            if part.strip()
        ]
        b.add_composition(
            composition_type="construction_template",
            construction_name=name,
            surface_pattern=pattern,
            category_code="CONSTRUCTION_TEMPLATE",
            category_name="Construction template",
            value_code=value_code.upper(),
            value_name=name,
            semantic_summary=name,
            derivation="source_template",
            locator=locator,
            components=components,
        )


def main() -> None:
    b = Builder()
    extract_standard_vowels(b)
    extract_ch3_ca(b)
    extract_slot_iv_vr(b)
    cases = extract_cases(b)
    extract_case_scope(b)
    extract_ch5(b)
    extract_ch6(b)
    extract_vx_degree_matrix(b)
    extract_affix_roots_and_degrees(b)
    generate_vxcs_compositions(b)
    generate_case_affix_compositions(b, cases)
    extract_register_and_suppletive_adjuncts(b, cases)
    extract_bias_adjuncts(b)
    extract_referentials(b)
    extract_number_roots(b)
    extract_ch10_roots(b)
    extract_explicit_root_paradigms(b)
    add_source_templates(b)
    b.write()
    print(
        " ".join(
            [
                f"atomic={len(b.atomic)}",
                f"compositions={len(b.compositions)}",
                f"components={len(b.components)}",
                f"assertions={len(b.assertions)}",
                f"categories={len(b.categories)}",
                f"affix_degrees={len(b.affix_degrees)}",
                f"root_senses={len(b.root_senses)}",
                f"allomorph_rules={len(b.allomorph_rules)}",
                f"affix_roots={len(b.affix_roots)}",
            ]
        )
    )


if __name__ == "__main__":
    main()

