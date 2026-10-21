#!/usr/bin/env python3
"""Extract source-grounded root/sense records from tracked lexicon page projections.

This is a source-corpus extractor only.  It deliberately does not assign Bilqis
token IDs, capabilities, grades, prerequisites, or mastery state.  The tracked
split PDFs are page-projection artifacts bound to the canonical New Ithkuil
lexicon source; they are not claimed to be byte-identical derivatives. Records
retain the canonical source identity plus the exact tracked artifact digest and
page locus used for extraction.
"""

from __future__ import annotations

import csv
import argparse
import contextlib
import hashlib
import io
import json
import sys
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
AVAILABLE_CHAPTERS = (*CHAPTERS,
    ChapterSource("3", "New Ithkuil Lexicon - Chapter 03 - Spacetime and Motion.pdf", "3.0"),
    ChapterSource("4", "New Ithkuil Lexicon - Chapter 04 - Psychology and Sociology.pdf", "4.0"),
    ChapterSource("5", "New Ithkuil Lexicon - Chapter 05 - Miscellaneous Entities.pdf", "5.0"),
    ChapterSource("6", "New Ithkuil Lexicon - Chapter 06 - Nature, Non-Biological.pdf", "6.0"),
    ChapterSource("7", "New Ithkuil Lexicon - Chapter 07 - Natural Phenomena.pdf", "7.0"),
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


def source_fingerprint(value: str) -> tuple[str, str]:
    """Return full-source hash and character count without copying long prose."""
    text = clean(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), str(len(text))


def example_excerpt(value: str, limit: int = 180) -> str:
    """Keep a short source example locator while the full wording stays in the PDF."""
    text = clean(value)
    match = re.search(r"(?:e\.g\.|for example)\s*[,;:]?\s*.*", text, re.IGNORECASE)
    return short_meaning(match.group(0), limit) if match else ""


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
        source_text = value[match.end():end].strip(" ;")
        if source_text:
            out.append((f"STEM {match.group(1)}", source_text))
    return out


def extract_table_senses(data: list[list[str | None]]) -> list[tuple[str, str, str, str]]:
    """Return (stem, specification, compact sense, full source text) from a root table."""
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
                source_text = clean(cell)
                summary = short_meaning(source_text)
                if summary:
                    senses.append((stem, spec, summary, source_text))
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
                    senses.extend(
                        (stem, label, short_meaning(source_text), source_text)
                        for stem, source_text in stem_senses
                    )
                elif joined:
                    senses.append(("", label, short_meaning(joined), joined))
            elif joined:
                senses.append(("", label, short_meaning(joined), joined))
            continue

        # Some compact lexical tables use one row per stem and no explicit
        # Specification rows.
        stem_match = re.fullmatch(r"STEM\s*([123])", label, re.IGNORECASE)
        if stem_match:
            summary = short_meaning(" ".join(clean(cell) for cell in row[1:] if clean(cell)))
            if summary:
                source_text = clean(" ".join(clean(cell) for cell in row[1:] if clean(cell)))
                senses.append((f"STEM {stem_match.group(1)}", "BSC", summary, source_text))

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


def extract_prose_senses(document, chapter: ChapterSource, root_loci: dict[tuple[int, str], dict[str, str]]):
    """Extract explicit Stem/Specification prose outside detected PDF tables.

    Several lexicon roots inherit the preceding root's Specification pattern and
    therefore appear as prose rather than as their own table.  The source still
    spells out their Stem 1/2/3 meanings.  Preserve those statements instead of
    making the table detector the accidental ontology boundary.
    """
    records: list[dict[str, str]] = []
    for local_page, page in enumerate(document, start=1):
        lines = [clean(line) for line in page.get_text("text").splitlines()]
        current_root: str | None = None
        marker: tuple[str, str] | None = None
        buffer: list[str] = []

        def flush() -> None:
            nonlocal marker, buffer
            if current_root and marker and buffer:
                locus = root_loci.get((local_page, current_root))
                if locus:
                    stem, specification = marker
                    source_text = clean(" ".join(buffer))
                    summary = short_meaning(source_text)
                    if summary:
                        source_text_sha256, source_text_char_count = source_fingerprint(
                            source_text
                        )
                        records.append(
                            {
                                "root_form_raw": current_root,
                                "stem": stem,
                                "specification": specification,
                                "sense_summary": summary,
                                "source_text_sha256": source_text_sha256,
                                "source_text_char_count": source_text_char_count,
                                "source_example_excerpt": example_excerpt(source_text),
                                "lexicon_chapter": chapter.chapter,
                                "lexicon_section": locus["lexicon_section"],
                                "source_pdf_page": str(local_page),
                                "source_printed_page": printed_page(page),
                                "source_table_index": "",
                                "source_locus_kind": "prose",
                            }
                        )
            marker = None
            buffer = []

        for line in lines:
            section_match = SECTION_RE.match(line)
            if section_match:
                flush()
                current_root = None
                continue
            root_match = ROOT_RE.match(line)
            if root_match:
                flush()
                form = root_match.group(1)
                current_root = form if (local_page, form) in root_loci else None
                continue
            if current_root is None:
                continue

            stem_match = re.match(r"^(?:BSC\s+)?Stem\s*([123])\s*:\s*(.*)$", line, re.IGNORECASE)
            if stem_match:
                flush()
                marker = (f"STEM {stem_match.group(1)}", "BSC")
                if stem_match.group(2):
                    buffer = [stem_match.group(2)]
                continue
            spec_match = re.match(r"^(CTE|CSV|OBJ)\s+(.*)$", line, re.IGNORECASE)
            if spec_match:
                flush()
                marker = ("", spec_match.group(1).upper())
                buffer = [spec_match.group(2)]
                continue
            if marker is None and line.lower().startswith("the three stems of this root"):
                marker = ("STEMS 1-3", "BSC")
                buffer = [line]
                continue
            if line.startswith("NOTE:") or line.startswith("The Specification pattern"):
                flush()
                continue
            if marker and line:
                buffer.append(line)
        flush()
    return records


def table_boundary_line(line: str) -> bool:
    return bool(
        re.match(r"^(?:STEM\s*[123]|BSC|CTE|CSV|OBJ)(?:\s|$)", line, re.IGNORECASE)
    )


def extract_numbered_stem_senses(
    document,
    chapter: ChapterSource,
    root_loci: dict[tuple[int, str], dict[str, str]],
) -> list[dict[str, str]]:
    """Extract compact numbered root-stem inventories.

    The lexicon uses a compact 1/2/3 presentation for families that explicitly
    inherit a preceding root's Specification pattern, including Chapter-2
    electronic-computer/program roots.  These numbered rows are source-stated
    Stem meanings, not prose examples, so preserve them as BSC Stem 1/2/3
    senses while retaining the inheritance statement separately as evidence.
    """
    records: list[dict[str, str]] = []
    numbered_re = re.compile(r"^([123])\.\s+(.+)$")

    for local_page, page in enumerate(document, start=1):
        lines = [clean(line) for line in page.get_text("text").splitlines()]
        current_root: str | None = None
        current_values: dict[str, str] = {}

        def flush() -> None:
            nonlocal current_values
            if current_root and set(current_values) == {"1", "2", "3"}:
                locus = root_loci.get((local_page, current_root))
                if locus:
                    for number in ("1", "2", "3"):
                        source_text = current_values[number]
                        source_text_sha256, source_text_char_count = source_fingerprint(
                            source_text
                        )
                        records.append(
                            {
                                "root_form_raw": current_root,
                                "stem": f"STEM {number}",
                                "specification": "BSC",
                                "sense_summary": short_meaning(source_text),
                                "source_text_sha256": source_text_sha256,
                                "source_text_char_count": source_text_char_count,
                                "source_example_excerpt": example_excerpt(source_text),
                                "lexicon_chapter": chapter.chapter,
                                "lexicon_section": locus["lexicon_section"],
                                "source_pdf_page": str(local_page),
                                "source_printed_page": printed_page(page),
                                "source_table_index": "",
                                "source_locus_kind": "compact_numbered_stem",
                            }
                        )
            current_values = {}

        for line in lines:
            section_match = SECTION_RE.match(line)
            if section_match:
                flush()
                current_root = None
                continue
            root_match = ROOT_RE.match(line)
            if root_match:
                flush()
                form = root_match.group(1)
                current_root = form if (local_page, form) in root_loci else None
                continue
            if current_root is None:
                continue

            match = numbered_re.match(line)
            if match:
                number, text = match.groups()
                if number == "1" and current_values:
                    flush()
                if number not in current_values:
                    current_values[number] = text
                continue

            # PyMuPDF may wrap one numbered meaning across physical lines.
            if current_values:
                if set(current_values) == {"1", "2", "3"}:
                    # The compact inventories normally emit each numbered
                    # meaning as one logical text line.  Once all three stems
                    # are present, a following non-numbered line is a note or
                    # derivational instruction, not part of Stem 3.
                    flush()
                    continue
                last = str(max(int(n) for n in current_values))
                if (
                    line
                    and not line.startswith(("NOTE:", "The stems of", "The Specifications"))
                    and not table_boundary_line(line)
                ):
                    current_values[last] = clean(current_values[last] + " " + line)
        flush()
    return records


def extract_root_evidence(
    document,
    chapter: ChapterSource,
    roots_by_form: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Capture short contextual evidence while retaining hashes of the full source prose.

    The tracked CSV deliberately does not reproduce long lexicon passages.  It
    keeps short locators/excerpts plus a digest and character count so a later
    researcher can re-open the exact tracked PDF page and verify the complete
    wording.  This catches source-level examples, scope restrictions, notes and
    inherited-Specification caveats that are semantically important but are not
    themselves Stem/Specification senses.
    """
    records: list[dict[str, str]] = []
    current_section: str | None = None
    current_root: str | None = None
    active_kind: str | None = None
    active_lines: list[str] = []
    active_page = ""
    active_printed = ""

    def flush() -> None:
        nonlocal active_kind, active_lines, active_page, active_printed
        if current_root and active_kind and active_lines:
            source_text = clean(" ".join(active_lines))
            if source_text:
                source_text_sha256, source_text_char_count = source_fingerprint(
                    source_text
                )
                locus = roots_by_form[current_root]
                records.append(
                    {
                        "lexicon_evidence_id": stable_id(
                            "LEXEVID",
                            SOURCE_ID,
                            current_root,
                            active_kind,
                            source_text_sha256,
                        ),
                        "lexicon_root_id": locus["lexicon_root_id"],
                        "root_form_raw": current_root,
                        "evidence_kind": active_kind,
                        "evidence_excerpt": short_meaning(source_text),
                        "source_text_sha256": source_text_sha256,
                        "source_text_char_count": source_text_char_count,
                        "lexicon_chapter": chapter.chapter,
                        "lexicon_section": locus["lexicon_section"],
                        "source_pdf_page": active_page,
                        "source_printed_page": active_printed,
                    }
                )
        active_kind = None
        active_lines = []
        active_page = ""
        active_printed = ""

    table_boundary = re.compile(
        r"^(?:STEM\s*[123]|BSC|CTE|CSV|OBJ)(?:\s|$)", re.IGNORECASE
    )

    for local_page, page in enumerate(document, start=1):
        pprinted = printed_page(page)
        for raw_line in page.get_text("text").splitlines():
            line = clean(raw_line)
            if not line:
                continue
            section_match = SECTION_RE.match(line)
            if section_match:
                flush()
                current_section = (
                    section_match.group(1)
                    if section_match.group(1).startswith(chapter.chapter + ".")
                    else None
                )
                if current_section is None:
                    current_root = None
                else:
                    # Chapter 1 introduces several special roots directly in
                    # the section heading (e.g. "1.3 The Copular Root: -Č-")
                    # and places scope prose before the repeated table heading.
                    # Attribute that prose to the root named by the section,
                    # rather than leaving the previous section's root active.
                    section_root = re.search(r"(-[^s]{1,14}-)(?:s|$)", line)
                    if section_root and section_root.group(1) in roots_by_form:
                        current_root = section_root.group(1)
                    elif current_root not in roots_by_form:
                        current_root = None
                continue
            root_match = ROOT_RE.match(line)
            if root_match:
                form = root_match.group(1)
                if form != current_root:
                    flush()
                current_root = form if (
                    current_section
                    and current_section.startswith(chapter.chapter + ".")
                    and form in roots_by_form
                ) else None
                continue
            if current_root is None:
                continue
            if table_boundary.match(line):
                flush()
                continue

            # A PDF bullet is often emitted as its own text line. Once a
            # scope restriction/note has started, keep its continuation
            # together even when that continuation contains "e.g."; the next
            # bullet/root/section/table boundary will flush it.
            if active_kind in {"scope_restriction", "scope_note"} and not line.startswith("•"):
                active_lines.append(line)
                continue

            lowered = line.lower()
            new_kind: str | None = None
            if line.startswith("•"):
                new_kind = "scope_restriction"
            elif lowered.startswith("the scope of this root") or "not to be used" in lowered:
                new_kind = "scope_note"
            elif line.upper().startswith("NOTE:"):
                new_kind = "note"
            elif lowered.startswith("the specification pattern") or lowered.startswith(
                "the specifications of"
            ):
                new_kind = "specification_note"
            elif "e.g." in lowered or "for example" in lowered:
                new_kind = "example_context"

            if new_kind:
                flush()
                active_kind = new_kind
                active_lines = [line]
                active_page = str(local_page)
                active_printed = pprinted
                continue
            if active_kind:
                active_lines.append(line)
        # A contextual note may continue onto the next page, so do not flush
        # merely because the page ended.
    flush()
    return records


def build(chapters=CHAPTERS) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    manifest = source_manifest_row()
    roots_by_id: dict[str, dict[str, str]] = {}
    senses_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    evidence_by_id: dict[str, dict[str, str]] = {}

    for chapter in chapters:
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
                    "evidence_status": ("official_source_observed" if chapter in CHAPTERS
                                        else "tracked_source_projection_observed"),
                }
            )
            roots_by_id.setdefault(row["lexicon_root_id"], row)

        root_loci = {(int(row["source_pdf_page"]), row["root_form_raw"]): row for row in chapter_roots}
        chapter_roots_by_form = {row["root_form_raw"]: row for row in chapter_roots}
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
                for stem, specification, summary, source_text in extract_table_senses(data):
                    sense_id = stable_id("LEXSENSE", SOURCE_ID, form, stem, specification, summary)
                    source_text_sha256, source_text_char_count = source_fingerprint(
                        source_text
                    )
                    senses_by_key.setdefault(
                        (form, stem, specification),
                        {
                            "lexicon_sense_id": sense_id,
                            "lexicon_root_id": locus["lexicon_root_id"],
                            "root_form_raw": form,
                            "stem": stem,
                            "specification": specification,
                            "sense_summary": summary,
                            "source_text_sha256": source_text_sha256,
                            "source_text_char_count": source_text_char_count,
                            "source_example_excerpt": example_excerpt(source_text),
                            "lexicon_chapter": chapter.chapter,
                            "lexicon_section": locus["lexicon_section"],
                            "source_pdf_page": str(local_page),
                            "source_printed_page": printed_page(page),
                            "source_table_index": str(table_index),
                            "source_locus_kind": "table",
                            "source_id": SOURCE_ID,
                            "source_url": manifest["final_url"],
                            "tracked_pdf_name": chapter.filename,
                            "tracked_pdf_sha256": split_digest,
                            "evidence_status": ("official_source_observed" if chapter in CHAPTERS
                                                else "tracked_source_projection_observed"),
                        },
                    )

        for prose in extract_prose_senses(document, chapter, root_loci):
            form = prose["root_form_raw"]
            stem = prose["stem"]
            specification = prose["specification"]
            key = (form, stem, specification)
            if key in senses_by_key:
                continue
            sense_id = stable_id("LEXSENSE", SOURCE_ID, form, stem, specification, prose["sense_summary"])
            senses_by_key[key] = {
                "lexicon_sense_id": sense_id,
                "lexicon_root_id": root_loci[(int(prose["source_pdf_page"]), form)]["lexicon_root_id"],
                **prose,
                "source_id": SOURCE_ID,
                "source_url": manifest["final_url"],
                "tracked_pdf_name": chapter.filename,
                "tracked_pdf_sha256": split_digest,
                "evidence_status": ("official_source_observed" if chapter in CHAPTERS
                                    else "tracked_source_projection_observed"),
            }

        for numbered in extract_numbered_stem_senses(document, chapter, root_loci):
            form = numbered["root_form_raw"]
            stem = numbered["stem"]
            specification = numbered["specification"]
            key = (form, stem, specification)
            if key in senses_by_key:
                continue
            sense_id = stable_id(
                "LEXSENSE",
                SOURCE_ID,
                form,
                stem,
                specification,
                numbered["sense_summary"],
            )
            senses_by_key[key] = {
                "lexicon_sense_id": sense_id,
                "lexicon_root_id": root_loci[
                    (int(numbered["source_pdf_page"]), form)
                ]["lexicon_root_id"],
                **numbered,
                "source_id": SOURCE_ID,
                "source_url": manifest["final_url"],
                "tracked_pdf_name": chapter.filename,
                "tracked_pdf_sha256": split_digest,
                "evidence_status": ("official_source_observed" if chapter in CHAPTERS
                                    else "tracked_source_projection_observed"),
            }

        for evidence in extract_root_evidence(
            document, chapter, chapter_roots_by_form
        ):
            evidence.update(
                {
                    "source_id": SOURCE_ID,
                    "source_url": manifest["final_url"],
                    "tracked_pdf_name": chapter.filename,
                    "tracked_pdf_sha256": split_digest,
                    "canonical_source_sha256": manifest["sha256"],
                    "evidence_status": ("official_source_observed" if chapter in CHAPTERS
                                        else "tracked_source_projection_observed"),
                }
            )
            evidence_by_id.setdefault(evidence["lexicon_evidence_id"], evidence)

    roots = sorted(roots_by_id.values(), key=lambda row: (int(row["lexicon_chapter"]), int(row["source_printed_page"] or 0), row["root_form_raw"]))
    senses = sorted(senses_by_key.values(), key=lambda row: (row["lexicon_root_id"], row["specification"], row["stem"], row["lexicon_sense_id"]))
    evidence = sorted(
        evidence_by_id.values(),
        key=lambda row: (
            row["lexicon_root_id"],
            int(row["source_pdf_page"] or 0),
            row["evidence_kind"],
            row["lexicon_evidence_id"],
        ),
    )
    return roots, senses, evidence


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty table {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def extract_snapshot(chapter_ids: tuple[str, ...], output: Path) -> dict:
    """Extract a separate, hash-bound source queue without changing live inputs.

    Later tracked page projections retain their own observed provenance. Their
    equivalence to the canonical full PDF needs a separate source comparison.
    Missing sense extraction remains visible source debt.
    """
    available = {chapter.chapter: chapter for chapter in AVAILABLE_CHAPTERS}
    if (not chapter_ids or len(set(chapter_ids)) != len(chapter_ids) or
            any(value not in available for value in chapter_ids)):
        raise ValueError("LEXICON_CHAPTER_SCOPE_INVALID")
    output = Path(output)
    if output.resolve() == DATA.resolve() or DATA.resolve() in output.resolve().parents:
        raise ValueError("LEXICON_EXPANSION_REQUIRES_SEPARATE_OUTPUT")
    chapters = tuple(available[value] for value in sorted(chapter_ids, key=int))
    roots, senses, evidence = build(chapters)
    files = {}
    for filename, rows in (("lexicon_roots.csv", roots),
                           ("lexicon_root_senses.csv", senses),
                           ("lexicon_root_evidence.csv", evidence)):
        if not rows:
            raise ValueError("LEXICON_EXTRACTION_EMPTY_TABLE:" + filename)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        files[filename] = stream.getvalue().encode("utf-8")
    sense_roots = {row["lexicon_root_id"] for row in senses}
    manifest = dict(
        schema="bilqis.ithkuil.lexicon-extraction/v1",
        chapters=[chapter.chapter for chapter in chapters],
        builder_sha256=sha256(Path(__file__)),
        canonical_source=source_manifest_row(),
        canonical_page_equivalence="NOT_MEASURED",
        input_files={chapter.filename: sha256(PDF_DIR / chapter.filename)
                     for chapter in chapters},
        output_files={name: hashlib.sha256(value).hexdigest()
                      for name, value in files.items()},
        root_count=len(roots), sense_count=len(senses), evidence_count=len(evidence),
        unresolved_root_ids=sorted(row["lexicon_root_id"] for row in roots
                                   if row["lexicon_root_id"] not in sense_roots),
        disposition="SOURCE_OBSERVATIONS_NOT_ADMITTED")
    files["lexicon_extraction_manifest.json"] = (
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    # Complete only matching partial writes; retain conflicting prior snapshots.
    if output.is_symlink():
        raise ValueError("LEXICON_EXTRACTION_OUTPUT_UNSAFE")
    for name, contents in files.items():
        path = output / name
        if path.is_symlink() or (path.exists() and (
                not path.is_file() or path.read_bytes() != contents)):
            raise ValueError("LEXICON_EXTRACTION_OUTPUT_IDENTITY_CHANGED:" + name)
    output.mkdir(parents=True, exist_ok=True)
    for name, contents in files.items():
        path = output / name
        if not path.exists():
            path.write_bytes(contents)
        if path.read_bytes() != contents:
            raise ValueError("LEXICON_EXTRACTION_READBACK_MISMATCH:" + name)
    return manifest


def verify_snapshot(output: Path) -> dict:
    """Verify completed extraction before selecting more source work."""
    manifest = json.loads((output / "lexicon_extraction_manifest.json").read_text())
    expected_names = {"lexicon_roots.csv", "lexicon_root_senses.csv", "lexicon_root_evidence.csv"}
    if (manifest.get("schema") != "bilqis.ithkuil.lexicon-extraction/v1" or
            set(manifest.get("output_files", {})) != expected_names or
            any((output / name).is_symlink() or
                sha256(output / name) != digest
                for name, digest in manifest["output_files"].items()) or
            any(sha256(PDF_DIR / name) != digest
                for name, digest in manifest["input_files"].items()) or
            manifest["canonical_source"] != source_manifest_row()):
        raise ValueError("LEXICON_EXTRACTION_SNAPSHOT_DRIFT")
    return manifest


def expand_next_snapshot(output_root: Path) -> dict:
    """Advance the source queue; chapter order never selects teaching order."""
    for chapter in AVAILABLE_CHAPTERS[len(CHAPTERS):]:
        output = output_root / ("chapter-" + chapter.chapter)
        manifest_path = output / "lexicon_extraction_manifest.json"
        if output.is_symlink() or manifest_path.is_symlink():
            raise ValueError("LEXICON_EXTRACTION_OUTPUT_UNSAFE")
        if manifest_path.exists():
            manifest = verify_snapshot(output)
            if manifest["chapters"] != [chapter.chapter]:
                raise ValueError("LEXICON_EXTRACTION_SNAPSHOT_SCOPE_DRIFT")
            continue
        manifest = extract_snapshot((chapter.chapter,), output)
        return dict(status="SOURCE_SNAPSHOT_EXTRACTED", output=str(output.resolve()),
                    manifest=manifest)
    return dict(status="TRACKED_SOURCE_QUEUE_EXHAUSTED")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapters", nargs="+", choices=tuple(
        chapter.chapter for chapter in AVAILABLE_CHAPTERS))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--next", action="store_true", help="Extract one unprocessed later chapter")
    args = parser.parse_args()
    if args.next:
        if args.output is None or args.chapters:
            parser.error("--next requires --output and cannot be combined with --chapters")
        with contextlib.redirect_stdout(sys.stderr):
            result = expand_next_snapshot(args.output)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return
    if args.chapters or args.output:
        if args.output is None:
            parser.error("--chapters requires --output to preserve canonical source tables")
        manifest = extract_snapshot(tuple(args.chapters or ("1", "2")), args.output)
        print(json.dumps(manifest, sort_keys=True, ensure_ascii=False))
        return
    roots, senses, evidence = build()
    write_csv(DATA / "lexicon_roots.csv", roots)
    write_csv(DATA / "lexicon_root_senses.csv", senses)
    write_csv(DATA / "lexicon_root_evidence.csv", evidence)
    print(
        f"lexicon roots={len(roots)} senses={len(senses)} evidence={len(evidence)}"
    )


if __name__ == "__main__":
    main()
