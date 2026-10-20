#!/usr/bin/env python3
"""Extract source-grounded root/sense records from the tracked split lexicon PDFs.

This is a source-corpus extractor only.  It deliberately does not assign Bilqis
token IDs, capabilities, grades, prerequisites, or mastery state.  The split
PDFs are tracked derivatives of the canonical New Ithkuil lexicon source;
records retain the canonical source identity plus the exact tracked derivative
hash and page locus used for extraction.
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - exercised only on unprepared hosts
    raise SystemExit(
        "PyMuPDF is required for lexicon extraction. Install lib/ithkuil/requirements-extraction.txt"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "_data" / "pdf"
DATA = ROOT / "_data" / "csv"
MANIFEST = DATA / "sources" / "source_manifest.csv"
SOURCE_ID = "NI-LEXICON-CURRICULUM"


@dataclass(frozen=True)
class ChapterSource:
    chapter: str
    filename: str
    first_section: str


CHAPTERS = (
    ChapterSource("1", "New Ithkuil Lexicon - Chapter 01 - Roots and Grammar.pdf", "1.0"),
    ChapterSource("2", "New Ithkuil Lexicon - Chapter 02 - Tools, States and Acts.pdf", "2.0"),
)

SECTION_TITLES = {
    "1.0": "Roots associated with grammatical functions",
    "1.1": "The Carrier Root",
    "1.2": "General Demonstrative Root",
    "1.3": "The Copular Root",
    "1.4": "Grammatical Terminology",
    "2.0": "Common States and Acts",
    "2.1": "Tool Use",
    "2.1.1": "Acts/Processes Accomplished by Means of Tools/Implements",
    "2.1.2": "Implements/Materials/Substances Used To Maintain Completed States Created via Tools/Devices/Machines/Manual Processes",
    "2.1.3": "Common Household Appliances and Electronic Devices",
    "2.1.4": "Objects/Implements Used to Hold/Contain Foodstuffs During Preparation, Cooking, and Serving",
    "2.1.5": "Fixtures Used To Facilitate/Maintain States Created via Tools/Devices/Machines/Manual Processes/Powered Processes",
    "2.1.6": "Furniture",
    "2.1.7": "Building",
}

ROOT_RE = re.compile(r"^(-[^\s]{1,14}-)(?:\s+(.*))?$")
SECTION_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)*)\b(?:\s+(.*))?$")
STEM_RE = re.compile(r"\bSTEM\s*([123])\s*:?\s*", re.IGNORECASE)
SPECIFICATIONS = {"BSC", "CTE", "CSV", "OBJ"}


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def short_meaning(value: str, limit: int = 180) -> str:
    text = clean(value)
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def stable_id(prefix: str, *parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:14]}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_manifest_row() -> dict[str, str]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["source_id"] == SOURCE_ID:
                return row
    raise RuntimeError(f"missing canonical lexicon source {SOURCE_ID}")


def printed_page(page) -> str:
    for line in page.get_text("text").splitlines():
        value = clean(line)
        if re.fullmatch(r"\d+", value):
            return value
    return ""


def split_stems(value: str) -> list[tuple[str, str]]:
    """Split one or more explicit STEM 1/2/3 labels from a table cell."""
    value = clean(value)
    matches = list(STEM_RE.finditer(value))
    if not matches:
        return []
    out: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        summary = value[match.end():end].strip(" ;")
        if summary:
            out.append((f"STEM {match.group(1)}", short_meaning(summary)))
    return out


def extract_table_senses(data: list[list[str | None]]) -> list[tuple[str, str, str]]:
    """Return (stem, specification, compact source sense) from a root table."""
    if not data:
        return []

    senses: list[tuple[str, str, str]] = []

    # Explicit 3-stem matrix: blank/STEM1/STEM2/STEM3 header followed by
    # BSC/CTE/CSV/OBJ rows.
    if len(data) >= 3 and len(data[1]) >= 4 and clean(data[1][0]) == "" and {
        clean(cell).upper() for cell in data[1][1:4]
    } == {"STEM 1", "STEM 2", "STEM 3"}:
        stems = [clean(cell).upper() for cell in data[1][1:4]]
        for row in data[2:]:
            spec = clean(row[0]).upper() if row else ""
            if spec not in SPECIFICATIONS:
                continue
            for stem, cell in zip(stems, row[1:4]):
                summary = short_meaning(clean(cell))
                if summary:
                    senses.append((stem, spec, summary))
        return senses

    # Three-column tables normally put all three BSC stems into the last two
    # cells, then use root-wide CTE/CSV/OBJ rows spanning the sense columns.
    for row in data[1:]:
        if not row:
            continue
        label = clean(row[0]).upper()
        if label in SPECIFICATIONS:
            joined = clean(" ".join(clean(cell) for cell in row[1:] if clean(cell)))
            if label == "BSC":
                stem_senses = split_stems(joined)
                if stem_senses:
                    senses.extend((stem, label, summary) for stem, summary in stem_senses)
                elif joined:
                    senses.append(("", label, short_meaning(joined)))
            elif joined:
                senses.append(("", label, short_meaning(joined)))
            continue

        # Some compact lexical tables use one row per stem and no explicit
        # Specification rows.
        stem_match = re.fullmatch(r"STEM\s*([123])", label, re.IGNORECASE)
        if stem_match:
            summary = short_meaning(" ".join(clean(cell) for cell in row[1:] if clean(cell)))
            if summary:
                senses.append((f"STEM {stem_match.group(1)}", "BSC", summary))

    return senses


def page_line_records(document, chapter: ChapterSource) -> tuple[list[dict[str, str]], dict[tuple[int, str], dict[str, str]]]:
    """Collect all root headings, including compact roots that have no table."""
    roots: list[dict[str, str]] = []
    lookup: dict[tuple[int, str], dict[str, str]] = {}
    current_section: str | None = None

    for local_page, page in enumerate(document, start=1):
        lines = [clean(line) for line in page.get_text("text").splitlines()]
        pprinted = printed_page(page)
        index = 0
        while index < len(lines):
            line = lines[index]
            section_match = SECTION_RE.match(line)
            if section_match:
                current_section = (
                    section_match.group(1)
                    if section_match.group(1).startswith(chapter.chapter + ".")
                    else None
                )
                index += 1
                continue
            if current_section is None or not current_section.startswith(chapter.chapter + "."):
                index += 1
                continue
            root_match = ROOT_RE.match(line)
            if not root_match:
                index += 1
                continue

            form = root_match.group(1)
            gloss = clean(root_match.group(2))
            if not gloss:
                # Compact category/root lists put the gloss on the next line.
                for next_line in lines[index + 1:index + 3]:
                    if next_line and not ROOT_RE.match(next_line) and not SECTION_RE.match(next_line):
                        gloss = next_line
                        break
            root_id = stable_id("LEXROOT", SOURCE_ID, form)
            row = {
                "lexicon_root_id": root_id,
                "root_form_raw": form,
                "root_form_normalized": form.strip("-").lower(),
                "root_gloss": short_meaning(gloss),
                "lexicon_chapter": chapter.chapter,
                "lexicon_section": current_section,
                "section_title": SECTION_TITLES.get(current_section, ""),
                "source_pdf_page": str(local_page),
                "source_printed_page": pprinted,
            }
            # One canonical source-root identity may be repeated inside the
            # split boundary. Keep the earliest locus in its owning chapter.
            if not any(existing["lexicon_root_id"] == root_id for existing in roots):
                roots.append(row)
                lookup[(local_page, form)] = row
            index += 1

    return roots, lookup


def build() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    manifest = source_manifest_row()
    roots_by_id: dict[str, dict[str, str]] = {}
    senses_by_id: dict[str, dict[str, str]] = {}

    for chapter in CHAPTERS:
        path = PDF_DIR / chapter.filename
        if not path.exists():
            raise RuntimeError(f"missing tracked split lexicon PDF: {path}")
        split_digest = sha256(path)
        document = fitz.open(path)
        chapter_roots, _lookup = page_line_records(document, chapter)

        for row in chapter_roots:
            row.update(
                {
                    "source_id": SOURCE_ID,
                    "source_url": manifest["final_url"],
                    "tracked_pdf_name": chapter.filename,
                    "tracked_pdf_sha256": split_digest,
                    "canonical_source_sha256": manifest["sha256"],
                    "evidence_status": "official_source_observed",
                }
            )
            roots_by_id.setdefault(row["lexicon_root_id"], row)

        root_loci = {(int(row["source_pdf_page"]), row["root_form_raw"]): row for row in chapter_roots}
        for local_page, page in enumerate(document, start=1):
            table_index = 0
            for table in page.find_tables().tables:
                table_index += 1
                data = table.extract()
                if not data:
                    continue
                first = clean(" ".join(clean(cell) for cell in data[0] if clean(cell)))
                match = re.search(r"(-[^\s]{1,14}-)(?:\s|$)", first)
                if not match:
                    continue
                form = match.group(1)
                locus = root_loci.get((local_page, form))
                if locus is None:
                    # Boundary-overlap or extraction-order anomaly: a root not
                    # owned by this chapter is deliberately ignored.
                    continue
                for stem, specification, summary in extract_table_senses(data):
                    sense_id = stable_id("LEXSENSE", SOURCE_ID, form, stem, specification, summary)
                    senses_by_id.setdefault(
                        sense_id,
                        {
                            "lexicon_sense_id": sense_id,
                            "lexicon_root_id": locus["lexicon_root_id"],
                            "root_form_raw": form,
                            "stem": stem,
                            "specification": specification,
                            "sense_summary": summary,
                            "lexicon_chapter": chapter.chapter,
                            "lexicon_section": locus["lexicon_section"],
                            "source_pdf_page": str(local_page),
                            "source_printed_page": printed_page(page),
                            "source_table_index": str(table_index),
                            "source_id": SOURCE_ID,
                            "source_url": manifest["final_url"],
                            "tracked_pdf_name": chapter.filename,
                            "tracked_pdf_sha256": split_digest,
                            "evidence_status": "official_source_observed",
                        },
                    )

    roots = sorted(roots_by_id.values(), key=lambda row: (int(row["lexicon_chapter"]), int(row["source_printed_page"] or 0), row["root_form_raw"]))
    senses = sorted(senses_by_id.values(), key=lambda row: (row["lexicon_root_id"], row["specification"], row["stem"], row["lexicon_sense_id"]))
    return roots, senses


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty table {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    roots, senses = build()
    write_csv(DATA / "lexicon_roots.csv", roots)
    write_csv(DATA / "lexicon_root_senses.csv", senses)
    print(f"lexicon roots={len(roots)} senses={len(senses)}")


if __name__ == "__main__":
    main()
