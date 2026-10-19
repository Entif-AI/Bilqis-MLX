#!/usr/bin/env python3
"""Extract source hierarchy and table structure from the New Ithkuil HTML.

This pass deliberately does not claim that every table row is a morpheme.
It builds the relational substrate used by later, stricter classifiers.
"""

from __future__ import annotations

import csv
import hashlib
import re
from bisect import bisect_right
from pathlib import Path

from lxml import html


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "_raw"
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "source_manifest.csv"

SECTION_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)+)\s*(?P<title>.*)$")
APPENDIX_RE = re.compile(r"^Appendix\s+(?P<letter>[A-Z])\s*:\s*(?P<title>.+)$", re.I)
CHAPTER_FILE_RE = re.compile(r"newithkuil_(?P<chapter>\d{2})_")


def clean(value: str | None, limit: int | None = None) -> str:
    text = " ".join((value or "").replace("\xa0", " ").split())
    if limit is not None and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def element_text(element, limit: int | None = None) -> str:
    return clean(" ".join(element.itertext()), limit=limit)


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_manifest() -> dict[str, dict[str, str]]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        return {row["local_name"]: row for row in csv.DictReader(handle)}


def section_id(source_id: str, number: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", number).strip("-")
    return f"{source_id}:{safe}"


def own_named_anchor(element) -> str:
    own = element.xpath(".//a[@name][1]/@name")
    return clean(own[0]) if own else ""


def nearest_named_anchor(element) -> str:
    own = own_named_anchor(element)
    if own:
        return own
    prior = element.xpath("preceding::a[@name][1]/@name")
    return clean(prior[0]) if prior else ""


def classify_table(rows: list[list[str]], context: str) -> str:
    if not rows:
        return "empty"
    flat = [cell for row in rows for cell in row if cell]
    if not flat:
        return "empty"
    joined = " ".join(flat).lower()
    navigation_terms = (
        "introduction", "phonology", "morpho-phonology", "case morphology",
        "verb morphology", "adjuncts", "referentials", "writing system", "numbers",
    )
    if sum(term in joined for term in navigation_terms) >= 4:
        return "navigation_or_layout"
    if any(term in joined for term in ("contents", "previous chapter", "next chapter")):
        return "navigation_or_layout"
    if len(rows) == 1:
        return "single_row"
    short_ratio = sum(len(cell) <= 80 for cell in flat) / len(flat)
    context_l = context.lower()
    paradigm_terms = (
        "affix", "case", "configuration", "affiliation", "perspective", "extension",
        "essence", "version", "function", "context", "valence", "mood", "aspect",
        "effect", "level", "phase", "sanction", "illocution", "validation", "referential",
        "vowel", "consonant", "stem", "specification", "degree", "bias", "register",
        "numeral", "number", "suffix", "slot", "form"
    )
    if short_ratio >= 0.75 and any(term in (joined[:700] + " " + context_l) for term in paradigm_terms):
        return "paradigm_or_inventory"
    if short_ratio >= 0.7:
        return "structured_table"
    return "mixed_or_explanatory"


def table_matrix(table) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.xpath(".//tr"):
        cells = [element_text(cell, limit=1000) for cell in tr.xpath("./th|./td")]
        if any(cells):
            rows.append(cells)
    return rows


def likely_header(row: list[str]) -> bool:
    if not row:
        return False
    text = " ".join(row).lower()
    terms = (
        "form", "value", "category", "meaning", "case", "degree", "type", "stem",
        "function", "configuration", "affiliation", "perspective", "extension", "essence",
        "valence", "mood", "aspect", "effect", "phase", "sanction", "validation",
        "illocution", "referent", "vowel", "consonant", "suffix", "number", "digit",
        "abbreviation", "name", "description", "slot"
    )
    return any(term in text for term in terms) and sum(len(c) <= 120 for c in row) >= max(1, len(row) // 2)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    sections: list[dict[str, str | int]] = []
    tables: list[dict[str, str | int]] = []
    cells: list[dict[str, str | int]] = []

    for local_name, source in manifest.items():
        if not local_name.endswith(".htm") or source["source_type"] == "grammar_index":
            continue
        path = RAW / local_name
        tree = html.parse(str(path))
        source_id = source["source_id"]
        chapter_match = CHAPTER_FILE_RE.search(local_name)
        chapter_number = str(int(chapter_match.group("chapter"))) if chapter_match else "APP"
        chapter_title = clean(source["title"].split(":", 1)[-1])

        candidate_by_number: dict[str, dict[str, str | int]] = {}
        for element in tree.xpath("//p|//h1|//h2|//h3|//h4|//h5|//h6"):
            text = element_text(element, limit=600)
            if not text:
                continue
            match = SECTION_RE.match(text)
            if match and (chapter_number == "APP" or match.group("number").split(".", 1)[0] == chapter_number):
                number = match.group("number")
                title = clean(match.group("title"), limit=300)
                source_heading_text = clean(match.group("title"), limit=600)
                if len(title) > 180 and ":" in title:
                    title = clean(title.split(":", 1)[0], limit=180)
                record = {
                    "section_id": section_id(source_id, number),
                    "source_id": source_id,
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "section_number": number,
                    "section_title": title,
                    "source_heading_text": source_heading_text,
                    "hierarchy_depth": number.count("."),
                    "parent_section_id": "",
                    "source_anchor": own_named_anchor(element),
                    "source_url": source["final_url"],
                    "source_line": element.sourceline or "",
                }
                prior = candidate_by_number.get(number)
                # Prefer an anchored occurrence and then the later body occurrence over a TOC echo.
                if prior is None or (record["source_anchor"] and not prior["source_anchor"]) or int(record["source_line"] or 0) > int(prior["source_line"] or 0):
                    candidate_by_number[number] = record
                continue
            if chapter_number == "APP":
                app = APPENDIX_RE.match(text)
                if app:
                    number = f"Appendix-{app.group('letter').upper()}"
                    candidate_by_number[number] = {
                        "section_id": section_id(source_id, number),
                        "source_id": source_id,
                        "chapter_number": "APP",
                        "chapter_title": chapter_title,
                        "section_number": number,
                        "section_title": clean(app.group("title"), limit=300),
                        "source_heading_text": clean(app.group("title"), limit=600),
                        "hierarchy_depth": 1,
                        "parent_section_id": "",
                        "source_anchor": own_named_anchor(element),
                        "source_url": source["final_url"],
                        "source_line": element.sourceline or "",
                    }

        page_sections = sorted(candidate_by_number.values(), key=lambda row: int(row["source_line"] or 0))
        by_number = {str(row["section_number"]): row for row in page_sections}
        for row in page_sections:
            number = str(row["section_number"])
            if number.startswith("Appendix-"):
                parent = ""
            else:
                parts = number.split(".")
                parent_num = ".".join(parts[:-1]) if len(parts) > 2 else f"{parts[0]}.0"
                parent = str(by_number[parent_num]["section_id"]) if parent_num in by_number and parent_num != number else ""
            row["parent_section_id"] = parent
        sections.extend(page_sections)

        line_starts = [int(row["source_line"] or 0) for row in page_sections]
        for table_index, table in enumerate(tree.xpath("//table"), start=1):
            matrix = table_matrix(table)
            line = table.sourceline or 0
            sec_idx = bisect_right(line_starts, line) - 1
            section = page_sections[sec_idx] if sec_idx >= 0 else None
            preceding = table.xpath("preceding::p[normalize-space()][1]")
            context = element_text(preceding[0], limit=300) if preceding else ""
            table_id = f"{source_id}:T{table_index:03d}"
            max_columns = max((len(row) for row in matrix), default=0)
            header = matrix[0] if matrix and likely_header(matrix[0]) else []
            tables.append(
                {
                    "table_id": table_id,
                    "source_id": source_id,
                    "section_id": section["section_id"] if section else "",
                    "chapter_number": chapter_number,
                    "section_number": section["section_number"] if section else "",
                    "context_label": context,
                    "table_role": classify_table(matrix, context),
                    "row_count": len(matrix),
                    "column_count": max_columns,
                    "header_row_detected": "true" if header else "false",
                    "header_text": " | ".join(header),
                    "source_url": source["final_url"],
                    "source_anchor": section["source_anchor"] if section else nearest_named_anchor(table),
                    "source_line": line,
                }
            )
            for row_index, row in enumerate(matrix, start=1):
                row_id = f"{table_id}:R{row_index:03d}"
                for column_index, value in enumerate(row, start=1):
                    if not value:
                        continue
                    header_value = header[column_index - 1] if header and column_index <= len(header) else ""
                    exact_cell_text = value if len(value) <= 200 else ""
                    cells.append(
                        {
                            "cell_id": f"{row_id}:C{column_index:02d}",
                            "row_id": row_id,
                            "table_id": table_id,
                            "source_id": source_id,
                            "section_id": section["section_id"] if section else "",
                            "row_index": row_index,
                            "column_index": column_index,
                            "header_value": header_value,
                            "cell_text": exact_cell_text,
                            "cell_text_sha256": text_sha256(value),
                            "cell_char_count": len(value),
                            "cell_text_truncated": "false" if exact_cell_text else "true",
                            "source_url": source["final_url"],
                            "source_line": line,
                        }
                    )

    write_csv(DATA / "source_sections.csv", sections)
    write_csv(DATA / "source_tables.csv", tables)
    write_csv(DATA / "source_table_cells.csv", cells)
    print(f"sections={len(sections)} tables={len(tables)} cells={len(cells)}")


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

