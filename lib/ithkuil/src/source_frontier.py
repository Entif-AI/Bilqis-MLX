"""Aggregate pinned Ithkuil source extraction receipts without rerunning parsers."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data" / "csv"
PINS = Path(__file__).with_name("lexicon_frontier_pins.json")
VERSION = "1.0.0"
STATUS = {"PARSED_COMPLETE_FOR_TRACKED_SLICE", "PARSED_WITH_DEBT", "PINNED_UNPARSED",
          "BLOCKED_SOURCE_IDENTITY", "UNSUPPORTED"}
CANONICAL_TABLES = {
    "source_sections": "section_id",
    "source_tables": "table_id",
    "source_table_cells": "cell_id",
    "lexicon_roots": "lexicon_root_id",
    "lexicon_root_senses": "lexicon_sense_id",
    "lexicon_root_evidence": "lexicon_evidence_id",
    "morphemes_atomic": "atomic_id",
    "morpheme_compositions": "composition_id",
    "composition_components": "component_id",
    "source_assertions": "assertion_id",
    "root_senses": "sense_id",
    "allomorph_rules": "allomorph_rule_id",
    "grammatical_categories": "category_id",
    "affix_degrees": "degree_id",
}
LEXICON_TABLES = ("lexicon_roots", "lexicon_root_senses", "lexicon_root_evidence")
GRAMMAR_TABLES = ("source_sections", "source_tables", "source_table_cells")
MORPHOLOGY_TABLES = ("morphemes_atomic", "morpheme_compositions", "composition_components",
                     "source_assertions", "root_senses", "allomorph_rules",
                     "grammatical_categories", "affix_degrees")


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha_file(path):
    path = Path(path)
    return _sha_bytes(path.read_bytes()) if path.is_file() else None


def _read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _row_digest(rows, table):
    key = CANONICAL_TABLES[table]
    stable = sorted(rows, key=lambda row: (row.get(key, ""), _json_bytes(row)))
    return _sha_bytes(_json_bytes(stable))


def _table_receipt(rows, table):
    return {"count": len(rows), "sha256": _row_digest(rows, table)}


def _table_rows(data_root):
    return {table: _read_csv(Path(data_root) / f"{table}.csv") for table in CANONICAL_TABLES}


def _csv_digest(rows, path):
    with Path(path).open(encoding="utf-8", newline="") as source:
        fields = next(csv.reader(source))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return _sha_bytes(stream.getvalue().encode("utf-8"))


def _by_source(tables, source_id, names):
    return {name: [row for row in tables[name] if row.get("source_id") == source_id]
            for name in names}


def _source_rows(tables, source_id, names):
    rows = {}
    for name in names:
        if name == "composition_components":
            continue
        owner = "primary_source_id" if name in {"morphemes_atomic", "morpheme_compositions"} else "source_id"
        if not tables[name] or owner in tables[name][0]:
            rows[name] = [row for row in tables[name] if row.get(owner) == source_id]
    return rows


def _table_receipts(rows):
    return {name: _table_receipt(value, name) for name, value in rows.items()}


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parser(name, version, path, **extra):
    return {"implementation": name, "version": version, "sha256": _sha_file(path), **extra}


def _identity(*values):
    return {"sha256": _sha_bytes(_json_bytes(values))}


def _source_entry(row, raw_root, tables, paths):
    source_id = row["source_id"]
    raw_path = Path(raw_root) / row["local_name"]
    observed = _sha_file(raw_path)
    pinned = row["sha256"] or None
    kind = row["source_type"]
    if kind.startswith("grammar_"):
        canonical = _source_rows(tables, source_id, GRAMMAR_TABLES + MORPHOLOGY_TABLES)
    elif source_id == "NI-LEXICON-CURRICULUM":
        canonical = {name: tables[name] for name in LEXICON_TABLES}
    elif source_id == "NI-AFFIX-PDF":
        canonical = _source_rows(tables, source_id, ("source_tables", "source_table_cells") + MORPHOLOGY_TABLES)
    else:
        canonical = {}
    debt = Counter()
    parser = None
    source_receipt = None
    scope = "Pinned source identity only; no parser output is admitted for this artifact."
    last_success = None

    if observed is None or observed != pinned:
        status = "BLOCKED_SOURCE_IDENTITY"
        debt["source_missing_or_digest_mismatch"] = 1
    elif kind in {"grammar_chapter", "grammar_appendix"} or kind == "grammar_index":
        parser = _parser("build_structure.py + build_morphology.py", "unversioned", paths["build_structure"],
                         morphology_sha256=_sha_file(paths["build_morphology"]))
        scope = "Structural sections, tables, and cells only; prose and semantic exhaustiveness are unmeasured."
        if sum(map(len, canonical.values())):
            status = "PARSED_WITH_DEBT"
            debt["prose_and_semantic_exhaustiveness_unmeasured"] = 1
        else:
            status = "PINNED_UNPARSED"
    elif source_id == "NI-LEXICON-SITE":
        status = "PINNED_UNPARSED"
    elif source_id == "NI-LEXICON-CURRICULUM":
        profile = _load_json(paths["lexicon_manifest"])
        versions = sorted({receipt["parser"]["version"] for receipt in profile["chapter_receipts"].values()})
        parser = _parser("build_lexicon_chapters.py + lexicon_frontier.py", ",".join(versions) or "unversioned",
                         paths["lexicon_frontier"], legacy_sha256=_sha_file(paths["build_lexicon_chapters"]))
        scope = "Canonical relational lexicon rows from bounded chapters 1–7; chapter 0 and full coverage remain unparsed."
        debt["chapter_0_toc_unparsed"] = 1
        debt["legacy_debt_not_measured"] = 2
        output_mismatch = any(
            profile["counts"].get(name) != len(tables[name])
            or profile["output_sha256"].get(f"{name}.csv") != _sha_file(Path(paths["data_root"]) / f"{name}.csv")
            for name in LEXICON_TABLES
        )
        if output_mismatch:
            debt["canonical_output_receipt_mismatch"] = 1
        status = ("BLOCKED_SOURCE_IDENTITY" if output_mismatch else
                  "PARSED_WITH_DEBT" if sum(map(len, canonical.values())) else "PINNED_UNPARSED")
        source_receipt = {"schema": profile["schema"], "counts": profile["counts"],
                          "admitted_chapters": profile["admitted_chapters"],
                          "output_sha256": profile["output_sha256"]}
        last_success = _identity(profile["output_sha256"],
                                 {number: value["accounting_sha256"]
                                  for number, value in profile["chapter_receipts"].items()})
    elif source_id == "NI-AFFIX-PDF":
        affix = _load_json(paths["affix_manifest"])
        receipt = affix["receipt"]
        parser = {"implementation": "affix_frontier.py", "version": receipt["parser_version"],
                  "sha256": receipt["parser_sha256"], "structure_parser_sha256": receipt["structure_parser_sha256"]}
        ledger = _load_json(paths["affix_accounting"])
        for item in ledger:
            if item.get("disposition") in {"UNSUPPORTED", "CONFLICT"}:
                debt[item.get("reason") or item["disposition"]] += 1
        scope = "Pinned affix table and text observations; source-only structure, no morphological relations inferred."
        outputs = affix["output_sha256"]
        expected_whole = {"source_sections.csv", "source_tables.csv", "source_table_cells.csv"}
        mismatch = any(outputs.get(name) != _sha_file(Path(paths["data_root"]) / name) for name in expected_whole)
        mismatch |= any(receipt["outputs"].get(name, {}).get("sha256") !=
                        _csv_digest(canonical[name.removesuffix(".csv")], Path(paths["data_root"]) / name)
                        for name in receipt["outputs"])
        ledger_sha = _sha_file(paths["affix_accounting"])
        expected_ledger_sha = outputs.get("sources/affix_frontier_accounting.json")
        mismatch |= ledger_sha is None or ledger_sha != expected_ledger_sha
        mismatch |= receipt.get("observations_sha256") != ledger_sha
        mismatch |= receipt["source_sha256"] != pinned
        mismatch |= receipt["counts"]["tables"] != len(canonical["source_tables"])
        mismatch |= receipt["counts"]["cells"] != len(canonical["source_table_cells"])
        table_dispositions = Counter(item.get("disposition") for item in ledger if item.get("kind") == "table")
        mismatch |= dict(table_dispositions) != receipt.get("table_dispositions")
        if mismatch:
            debt["affix_output_or_ledger_receipt_mismatch"] += 1
        status = "BLOCKED_SOURCE_IDENTITY" if mismatch else (
            "PARSED_WITH_DEBT" if canonical["source_tables"] else "PINNED_UNPARSED")
        last_success = _identity(receipt["source_sha256"], receipt["parser_sha256"], receipt["structure_parser_sha256"], receipt["outputs"])
        source_receipt = receipt
        paths["input_files"]["sources/affix_frontier_manifest.json"] = _sha_file(paths["affix_manifest"])
        paths["input_files"]["sources/affix_frontier_accounting.json"] = _sha_file(paths["affix_accounting"])
    else:
        status = "PINNED_UNPARSED"

    paths["input_files"][f"_raw/{row['local_name']}"] = observed
    return {
        "source_id": source_id, "artifact_id": source_id, "kind": kind,
        "pinned_sha256": pinned, "observed_sha256": observed, "status": status,
        "parser": parser, "scope": scope, "canonical_rows": _table_receipts(canonical),
        "debt_by_reason": dict(sorted(debt.items())), "last_success_identity": last_success,
        "source_receipt": source_receipt,
    }


def _chapter_entry(number, pin, pins_source_id, pdf_root, tables, profile, accounting_root, paths):
    artifact_id = f"{pins_source_id}:CHAPTER:{number}"
    path = Path(pdf_root) / pin["filename"]
    observed = _sha_file(path)
    source_receipt = profile["chapter_receipts"].get(number)
    admitted = number in profile["admitted_chapters"]
    canonical = {name: [row for row in tables[name] if row.get("lexicon_chapter") == number]
                 for name in LEXICON_TABLES}
    debt = Counter()
    parser = None
    last_success = None

    if observed is None or observed != pin["sha256"]:
        status = "BLOCKED_SOURCE_IDENTITY"
        debt["source_missing_or_digest_mismatch"] = 1
    elif source_receipt is not None and source_receipt.get("source", {}).get("sha256") != pin["sha256"]:
        status = "BLOCKED_SOURCE_IDENTITY"
        debt["chapter_receipt_source_digest_mismatch"] = 1
    elif number == "0":
        status = "PINNED_UNPARSED"
    elif number in {"1", "2"}:
        parser = _parser("build_lexicon_chapters.py", "unversioned", paths["build_lexicon_chapters"])
        debt["legacy_debt_not_measured"] = 1
        status = "PARSED_WITH_DEBT" if sum(map(len, canonical.values())) else "PINNED_UNPARSED"
    elif not admitted or source_receipt is None:
        status = "PINNED_UNPARSED" if not sum(map(len, canonical.values())) else "BLOCKED_SOURCE_IDENTITY"
        if status == "BLOCKED_SOURCE_IDENTITY":
            debt["canonical_rows_without_admission_receipt"] = 1
    else:
        ledger_path = Path(accounting_root) / f"chapter-{number}-accounting.json"
        ledger_sha = _sha_file(ledger_path)
        paths["input_files"][f"sources/lexicon_frontier/chapter-{number}-accounting.json"] = ledger_sha
        if ledger_sha is None or ledger_sha != source_receipt["accounting_sha256"]:
            status = "BLOCKED_SOURCE_IDENTITY"
            debt["accounting_receipt_digest_mismatch"] = 1
        else:
            ledger = _load_json(ledger_path)
            debt.update(item["status"] for item in ledger
                        if item.get("status", "").startswith("DEBT_"))
            if source_receipt.get("counts", {}).get("roots_without_senses", 0):
                debt["roots_without_parsed_senses_in_source_receipt"] = source_receipt["counts"]["roots_without_senses"]
            parser_data = source_receipt["parser"]
            parser = {"implementation": "lexicon_frontier.py", "version": parser_data["version"],
                      "sha256": parser_data["sha256"], "legacy_sha256": parser_data["legacy_sha256"]}
            status = "PARSED_WITH_DEBT" if debt else "PARSED_COMPLETE_FOR_TRACKED_SLICE"
            last_success = _identity(source_receipt["source"]["sha256"], source_receipt["accounting_sha256"],
                                     parser_data["sha256"], source_receipt["output_sha256"])
            paths["input_files"][f"sources/lexicon_frontier/chapter-{number}-accounting.json"] = ledger_sha

    paths["input_files"][f"_data/pdf/{pin['filename']}"] = observed
    return {
        "source_id": pins_source_id, "artifact_id": artifact_id, "kind": "lexicon_chapter_slice",
        "pinned_sha256": pin["sha256"], "observed_sha256": observed, "status": status,
        "parser": parser,
        "scope": f"Lexicon chapter {number} slice; source-observation counts are not canonical first-observation row counts.",
        "canonical_rows": _table_receipts(canonical), "source_receipt": source_receipt,
        "debt_by_reason": dict(sorted(debt.items())), "last_success_identity": last_success,
    }


def generate(data_root=DATA, pins_path=PINS):
    """Return a deterministic receipt from current pins, ledgers, and canonical CSVs."""
    data_root = Path(data_root)
    ithkuil = data_root.parent.parent
    raw_root = ithkuil / "_raw"
    pdf_root = data_root.parent / "pdf"
    source_manifest_path = data_root / "sources" / "source_manifest.csv"
    pins_path = Path(pins_path)
    source_rows = _read_csv(source_manifest_path)
    ids = [row["source_id"] for row in source_rows]
    if len(ids) != 18 or len(set(ids)) != len(ids):
        raise ValueError("source_manifest must contain 18 unique source identities")
    pins = _load_json(pins_path)
    source_pdfs = pins["source_pdfs"]
    if set(source_pdfs) != {str(number) for number in range(8)}:
        raise ValueError("lexicon pins must contain split artifacts 0 through 7")
    tables = _table_rows(data_root)
    paths = {
        "build_structure": ROOT / "src" / "build_structure.py",
        "build_morphology": ROOT / "src" / "build_morphology.py",
        "build_lexicon_chapters": ROOT / "src" / "build_lexicon_chapters.py",
        "lexicon_frontier": ROOT / "src" / "lexicon_frontier.py",
        "lexicon_manifest": data_root / "sources" / "lexicon_frontier_manifest.json",
        "affix_manifest": data_root / "sources" / "affix_frontier_manifest.json",
        "affix_accounting": data_root / "sources" / "affix_frontier_accounting.json",
        "input_files": {},
    }
    profile = _load_json(paths["lexicon_manifest"])
    paths["input_files"]["sources/source_manifest.csv"] = _sha_file(source_manifest_path)
    paths["input_files"]["sources/lexicon_frontier_manifest.json"] = _sha_file(paths["lexicon_manifest"])
    paths["input_files"]["lexicon_frontier_pins.json"] = _sha_file(pins_path)
    for table in CANONICAL_TABLES:
        paths["input_files"][f"{table}.csv"] = _sha_file(data_root / f"{table}.csv")
    paths["data_root"] = data_root

    entries = [_source_entry(row, raw_root, tables, paths) for row in source_rows]
    entries.extend(_chapter_entry(number, source_pdfs[number], pins["source_id"], pdf_root,
                                  tables, profile, data_root / "sources" / "lexicon_frontier", paths)
                   for number in sorted(source_pdfs, key=int))
    entries.sort(key=lambda item: (item["source_id"], item["artifact_id"]))
    if len(entries) != len(source_rows) + len(source_pdfs):
        raise ValueError("frontier entry reconciliation failed")

    roots = tables["lexicon_roots"]
    senses = tables["lexicon_root_senses"]
    evidence = tables["lexicon_root_evidence"]
    roots_with_senses = {row["lexicon_root_id"] for row in senses}
    by_chapter = {}
    for number in map(str, range(8)):
        chapter_roots = [row for row in roots if row.get("lexicon_chapter") == number]
        chapter_senses = [row for row in senses if row.get("lexicon_chapter") == number]
        chapter_evidence = [row for row in evidence if row.get("lexicon_chapter") == number]
        by_chapter[number] = {
            "roots": len(chapter_roots), "senses": len(chapter_senses), "evidence": len(chapter_evidence),
            "roots_without_parsed_senses": sum(row["lexicon_root_id"] not in roots_with_senses for row in chapter_roots),
        }

    affix_manifest = _load_json(paths["affix_manifest"])
    affix_receipt = affix_manifest["receipt"]
    affix_ledger = _load_json(paths["affix_accounting"])
    table_ledger = [item for item in affix_ledger if item.get("kind") == "table"]
    affix_entry = next(item for item in entries if item["source_id"] == "NI-AFFIX-PDF")
    affix_canonical = affix_entry["canonical_rows"]
    affix_debt = Counter(item.get("reason") or item.get("disposition") for item in affix_ledger
                         if item.get("disposition") in {"UNSUPPORTED", "CONFLICT"})
    grammar_counts = {table: sum(1 for row in tables[table]
                                 if row.get("source_id") != "NI-AFFIX-PDF") for table in GRAMMAR_TABLES}
    aggregate_debt = Counter()
    for entry in entries:
        debt = entry["debt_by_reason"]
        if entry["artifact_id"] == "NI-LEXICON-CURRICULUM":
            debt = {reason: count for reason, count in debt.items()
                    if reason != "legacy_debt_not_measured"}
        aggregate_debt.update(debt)
    aggregate_debt["roots_without_parsed_senses"] = len(roots) - len(roots_with_senses)
    unparsed = [entry["artifact_id"] for entry in entries
                if entry["status"] in {"PINNED_UNPARSED", "BLOCKED_SOURCE_IDENTITY", "UNSUPPORTED"}]

    receipt = {
        "schema": "bilqis.ithkuil.extraction-frontier/v1", "version": VERSION,
        "generator": {"implementation": "source_frontier.py", "version": VERSION,
                      "sha256": _sha_file(Path(__file__))},
        "inputs": dict(sorted(paths["input_files"].items())),
        "reconciliation": {"source_manifest_entries": len(source_rows), "split_chapter_entries": len(source_pdfs),
                           "entry_count": len(entries)},
        "claims": {"full_new_ithkuil_coverage": False, "semantic_admission": False,
                   "curriculum_admission": False},
        "aggregates": {
            "grammar": {"structural_rows": grammar_counts, "semantic_exhaustiveness_measured": False,
                        "semantic_exhaustiveness_debt": 1},
            "morphology": {table: _table_receipt(tables[table], table) for table in MORPHOLOGY_TABLES},
            "lexicon": {"roots": len(roots), "senses": len(senses), "evidence": len(evidence),
                        "roots_without_parsed_senses": len(roots) - len(roots_with_senses),
                        "chapters": by_chapter},
            "affix": {"parsed_tables": affix_canonical["source_tables"]["count"],
                      "parsed_cells": affix_canonical["source_table_cells"]["count"],
                      "unsupported_tables": sum(item.get("disposition") == "UNSUPPORTED" for item in table_ledger),
                      "conflicting_tables": sum(item.get("disposition") == "CONFLICT" for item in table_ledger),
                      "unsupported_observations": sum(item.get('disposition') == 'UNSUPPORTED'
                                                      for item in affix_ledger),
                      "debt_by_reason": dict(sorted(affix_debt.items())),
                      "semantic_relationships_inferred": False},
            "debt": {"by_reason": dict(sorted(aggregate_debt.items()))},
            "unparsed_artifact_ids": unparsed,
        },
        "entries": entries,
    }
    receipt["receipt_sha256"] = _sha_bytes(_json_bytes(receipt))
    return receipt


def render_markdown(receipt):
    """Render the human summary only from a generated receipt."""
    agg = receipt["aggregates"]
    lex = agg["lexicon"]
    affix = agg["affix"]
    lines = ["# Ithkuil Extraction Frontier", "", "Generated from the machine-readable extraction frontier receipt.", "",
             f"Full New Ithkuil coverage: {'yes' if receipt['claims']['full_new_ithkuil_coverage'] else 'no'}",
             f"Semantic admission: {'yes' if receipt['claims']['semantic_admission'] else 'no'}",
             f"Curriculum admission: {'yes' if receipt['claims']['curriculum_admission'] else 'no'}", "",
             "## Canonical lexicon", "",
             f"Roots: {lex['roots']}. Senses: {lex['senses']}. Evidence rows: {lex['evidence']}.",
             f"Roots without parsed senses: {lex['roots_without_parsed_senses']}.", "",
             "| Chapter | Roots | Senses | Evidence | Roots without senses | Status |",
             "|---:|---:|---:|---:|---:|---|"]
    for number, counts in lex["chapters"].items():
        entry = next(item for item in receipt["entries"]
                     if item["artifact_id"].endswith(f":CHAPTER:{number}"))
        lines.append(f"| {number} | {counts['roots']} | {counts['senses']} | {counts['evidence']} | "
                     f"{counts['roots_without_parsed_senses']} | {entry['status']} |")
    lines.extend(["", "## Grammar and morphology", "",
                  f"Grammar structural rows: {agg['grammar']['structural_rows']}. Prose and semantic exhaustiveness are unmeasured.",
                  f"Morphology rows: {agg['morphology']['morphemes_atomic']['count']} atomic morphemes; "
                  f"{agg['morphology']['affix_degrees']['count']} affix degrees.", "",
                  "## Affix source", "",
                  f"Parsed tables: {affix['parsed_tables']}. Parsed cells: {affix['parsed_cells']}. "
                  f"Unsupported tables: {affix['unsupported_tables']}. Conflicting tables held: {affix['conflicting_tables']}.",
                  "Semantic relationships inferred: no.", "",
                  "## Debt", "",
                  "| Reason | Count |", "|---|---:|"])
    lines.extend(f"| {reason} | {count} |" for reason, count in agg["debt"]["by_reason"].items())
    lines.extend(["", "## Unparsed or blocked artifacts", ""])
    lines.extend(f"- {artifact_id}" for artifact_id in agg["unparsed_artifact_ids"])
    lines.extend(["", f"Receipt SHA-256: `{receipt['receipt_sha256']}`", ""])
    return "\n".join(lines)


def _atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(value)
    os.replace(temporary, path)
    if path.read_bytes() != value:
        raise OSError(f"readback mismatch: {path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare generated receipt and Markdown without writing")
    args = parser.parse_args(argv)
    receipt = generate()
    receipt_bytes = _json_bytes(receipt)
    markdown_bytes = render_markdown(receipt).encode("utf-8")
    receipt_path = DATA / "sources" / "extraction_frontier.json"
    markdown_path = ROOT / "EXTRACTION_FRONTIER.md"
    if args.check:
        valid = receipt_path.is_file() and markdown_path.is_file()
        valid = valid and receipt_path.read_bytes() == receipt_bytes and markdown_path.read_bytes() == markdown_bytes
        print("source frontier receipt and Markdown are current" if valid else "source frontier output drift or missing")
        return 0 if valid else 1
    _atomic_write(markdown_path, markdown_bytes)
    _atomic_write(receipt_path, receipt_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
