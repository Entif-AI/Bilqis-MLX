"""Pinned PDF observations in the existing source-table IR; no morphology inference."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import fitz

if __package__:
    from .build_structure import classify_table, clean, text_sha256
else:
    from build_structure import classify_table, clean, text_sha256

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "_raw" / "newithkuil_affixes.pdf"
SOURCE_ID = "NI-AFFIX-PDF"
SOURCE_URL = "https://www.ithkuil.net/newithkuil_affixes.pdf"
PIN = "5b758ff4c79ba6ccb6e241e59507f7849a7c470c4b34b431bf546cd028aea3aa"
PARSER_VERSION = "1.0.0"
CODE = re.compile(r"^([A-Z][A-Z0-9]{2})(\*)?(?:\s|$)")
TABLE_FIELDS = (
    "table_id", "source_id", "section_id", "chapter_number", "section_number",
    "context_label", "table_role", "row_count", "column_count", "header_row_detected",
    "header_text", "header_text_sha256", "header_char_count", "header_text_truncated",
    "source_url", "source_anchor", "source_line",
)
CELL_FIELDS = (
    "cell_id", "row_id", "table_id", "source_id", "section_id", "row_index", "column_index",
    "header_value", "header_value_sha256", "header_value_char_count", "header_value_truncated",
    "cell_text", "cell_text_sha256", "cell_char_count", "cell_text_truncated", "source_url", "source_line",
)


@dataclass(frozen=True)
class ParsedTable:
    code: str
    form: str
    caption: str
    header_columns: tuple[int, int]
    degrees: dict[int, tuple[int, str, int, int]]


@dataclass
class Extraction:
    tables: list[dict]
    cells: list[dict]
    observations: list[dict]
    receipt: dict


def parse_table(matrix: list[list[str | None]]) -> ParsedTable | None:
    """Admit only complete explicit nine-degree blocks with unambiguous headers."""
    if len(matrix) != 10:
        return None
    header = [(i, clean(value)) for i, value in enumerate(matrix[0]) if clean(value)]
    if len(header) != 2:
        return None
    forms = [(i, text) for i, text in header if re.fullmatch(r"-[^\W\d_]+", text)]
    captions = [(i, text, CODE.match(text)) for i, text in header if CODE.match(text)]
    if len(forms) != 1 or len(captions) != 1:
        return None
    degrees = {}
    for row_number, row in enumerate(matrix[1:], 2):
        values = [(i, clean(value)) for i, value in enumerate(row) if clean(value)]
        if len(values) != 2 or values[0][1] not in set("123456789"):
            return None
        degree = int(values[0][1])
        if degree in degrees:
            return None
        degrees[degree] = (row_number, values[1][1], values[0][0] + 1, values[1][0] + 1)
    if set(degrees) != set(range(1, 10)):
        return None
    return ParsedTable(captions[0][2].group(1), forms[0][1], captions[0][1],
                       (forms[0][0] + 1, captions[0][0] + 1), degrees)


def canonical_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def row_sha256(row: dict) -> str:
    return hashlib.sha256(canonical_bytes({key: str(value) for key, value in row.items()})).hexdigest()


def csv_bytes(rows: list[dict], fields: tuple[str, ...]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def output_bytes(extraction: Extraction) -> dict[str, bytes]:
    return {"source_tables.csv": csv_bytes(extraction.tables, TABLE_FIELDS),
            "source_table_cells.csv": csv_bytes(extraction.cells, CELL_FIELDS)}


def _compact(text: str, prefix: str) -> dict:
    return {prefix: text if len(text) <= 200 else "",
            f"{prefix}_sha256": text_sha256(text) if text else "",
            f"{prefix}_char_count": len(text),
            f"{prefix}_truncated": "true" if len(text) > 200 else "false"}


def _bbox(box) -> list[float] | None:
    return [round(float(value), 6) for value in box] if box is not None else None


def extract(pdf_path: Path = PDF, *, expected_sha256: str = PIN,
            source_url: str = SOURCE_URL) -> Extraction:
    """Extract without publishing. A mismatched source never reaches the PDF engine."""
    pdf_path = Path(pdf_path)
    source_bytes = pdf_path.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"affix source pin mismatch: {digest} != {expected_sha256}")
    tables, cells, observations, candidates = [], [], [], []
    inventory = Counter()
    declared_codes = Counter()
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        page_count = len(document)
        pdf_format = document.metadata.get('format', '')
        for page_number, page in enumerate(document, 1):
            found = page.find_tables().tables
            boxes = [fitz.Rect(table.bbox) for table in found]
            for table_number, table in enumerate(found, 1):
                matrix = [[clean(value) for value in row] for row in table.extract()]
                parsed = parse_table(matrix)
                # A partial block can still explicitly redeclare a candidate's key.
                header = [value for value in matrix[0] if value] if matrix else []
                if len(header) == 2 and any(re.fullmatch(r'-[^\W\d_]+', value) for value in header):
                    declared_codes.update(CODE.match(value).group(1) for value in header if CODE.match(value))
                shape = f"{len(matrix)}x{max(map(len, matrix), default=0)}"
                inventory[shape] += 1
                observation = {"kind": "table", "page": page_number, "table": table_number,
                               "bbox": _bbox(table.bbox),
                               "matrix_sha256": hashlib.sha256(canonical_bytes(matrix)).hexdigest(), "shape": shape,
                               "disposition": "CANDIDATE" if parsed else "UNSUPPORTED",
                               "reason": "complete_explicit_degree_block" if parsed else "unsupported_table_shape"}
                observations.append(observation)
                if parsed:
                    observation["code"] = parsed.code
                    cell_boxes = [[_bbox(box) for box in row.cells] for row in table.rows]
                    candidates.append((parsed, matrix, cell_boxes, observation))
            for block_index, block in enumerate(page.get_text("dict")["blocks"], 1):
                for line_index, line in enumerate(block.get("lines", []), 1):
                    for span_index, span in enumerate(line["spans"], 1):
                        text = clean(span["text"])
                        if not text:
                            continue
                        box = fitz.Rect(span["bbox"])
                        overlaps = [i for i, table_box in enumerate(boxes, 1) if box.intersects(table_box)]
                        covered = [i for i, table_box in enumerate(boxes, 1) if table_box.contains(box)]
                        observations.append({"kind": "text_span", "page": page_number,
                                             "block": block_index, "line": line_index, "span": span_index,
                                             "bbox": _bbox(box), "text": text if len(text) <= 200 else "",
                                             "text_sha256": text_sha256(text), "text_char_count": len(text),
                                             "covering_tables": covered, "overlapping_tables": overlaps,
                                             "disposition": "TABLE_COVERED" if covered else "UNSUPPORTED",
                                             "reason": "table_text" if covered else
                                             "partial_table_overlap" if overlaps else "unclassified_source_prose"})
    for parsed, matrix, boxes, observation in candidates:
        if declared_codes[parsed.code] != 1:
            observation.update(disposition="CONFLICT", reason="repeated_affix_identity")
            continue
        used = [(1, column) for column in parsed.header_columns]
        used.extend((row, column) for row, _, label, meaning in parsed.degrees.values()
                    for column in (label, meaning))
        if any(not boxes[row - 1][column - 1] for row, column in used):
            observation.update(disposition='UNSUPPORTED', reason='ambiguous_cell_locus')
            continue
        table_id = f"{SOURCE_ID}:AFFIX:{parsed.code}"
        header = " | ".join(matrix[0])
        table_row = {"table_id": table_id, "source_id": SOURCE_ID, "section_id": "",
                     "chapter_number": "", "section_number": "", "context_label": clean(parsed.caption, 180),
                     "table_role": classify_table(matrix, parsed.caption), "row_count": len(matrix),
                     "column_count": max(map(len, matrix)), "header_row_detected": "true",
                     "header_text": header if len(header) <= 200 else "",
                     "header_text_sha256": text_sha256(header), "header_char_count": len(header),
                     "header_text_truncated": "true" if len(header) > 200 else "false",
                     "source_url": source_url, "source_anchor": f"page={observation['page']}", "source_line": ""}
        tables.append(table_row)
        observation.update(disposition="PARSED", output_id=table_id, output_table="source_tables.csv",
                           row_sha256=row_sha256(table_row))
        roles = [(1, parsed.header_columns[0], "HEADER", "FORM", parsed.form),
                 (1, parsed.header_columns[1], "HEADER", "CAPTION", parsed.caption)]
        for degree, (row_number, meaning, label_column, meaning_column) in sorted(parsed.degrees.items()):
            roles.extend([(row_number, label_column, f"DEGREE:{degree}", "LABEL", str(degree)),
                          (row_number, meaning_column, f"DEGREE:{degree}", "MEANING", meaning)])
        for row_number, column, row_key, role, text in roles:
            row_id = f"{table_id}:{row_key}"
            header_value = matrix[0][column - 1] if column <= len(matrix[0]) else ""
            row = {"cell_id": f"{row_id}:{role}", "row_id": row_id, "table_id": table_id,
                   "source_id": SOURCE_ID, "section_id": "", "row_index": row_number,
                   "column_index": column, **_compact(header_value, "header_value"),
                   "cell_text": text if len(text) <= 200 else "", "cell_text_sha256": text_sha256(text),
                   "cell_char_count": len(text), "cell_text_truncated": "true" if len(text) > 200 else "false",
                   "source_url": source_url, "source_line": ""}
            cells.append(row)
            observations.append({"kind": "cell", "page": observation["page"], "table": observation["table"],
                                 "row": row_number, "column": column, "bbox": boxes[row_number - 1][column - 1],
                                 "text": text if len(text) <= 200 else "", "text_sha256": text_sha256(text),
                                 "text_char_count": len(text), "disposition": "PARSED", "role": role,
                                 "output_table": "source_table_cells.csv", "output_id": row["cell_id"],
                                 "row_sha256": row_sha256(row)})
    tables.sort(key=lambda row: row["table_id"])
    cells.sort(key=lambda row: row["cell_id"])
    result = Extraction(tables, cells, observations, {})
    result.receipt = {
        "schema": "ithkuil.affix_frontier.receipt.v1", "source_id": SOURCE_ID,
        "source_url": source_url, "source_pdf": pdf_path.name, "source_sha256": digest,
        "source_bytes": len(source_bytes), "page_count": page_count, "pdf_format": pdf_format,
        "parser_version": PARSER_VERSION, "parser_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "structure_parser_sha256": hashlib.sha256((ROOT / 'src/build_structure.py').read_bytes()).hexdigest(),
        "engine": "PyMuPDF", "engine_version": fitz.VersionBind,
        "inventory": {"detected_tables": sum(inventory.values()), "table_shapes": dict(sorted(inventory.items()))},
        "counts": {"tables": len(tables), "cells": len(cells), "observations": len(observations)},
        "dispositions": dict(sorted(Counter(row["disposition"] for row in observations).items())),
        "table_dispositions": dict(sorted(Counter(row["disposition"] for row in observations if row["kind"] == "table").items())),
        "observations_sha256": hashlib.sha256(canonical_bytes(observations)).hexdigest(),
        "outputs": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                    for name, data in output_bytes(result).items()},
        "semantic_relationships_inferred": False,
    }
    return result
