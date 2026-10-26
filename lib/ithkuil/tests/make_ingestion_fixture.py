"""Mechanically select real canonical rows and one pinned parent-table excerpt.

Authoring tool only; clean-room execution consumes the checked-in output and
never reads the production corpus or ignored snapshots through this tool.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from lxml import etree, html

from lib.ithkuil.src.build_structure import table_matrix
from lib.ithkuil.src.skos.preflight_manifest import load_manifest


LIB = Path(__file__).resolve().parents[1]
SOURCE = LIB / "_data/csv"
TARGET = Path(__file__).parent / "fixtures/ingestion"


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def main():
    manifest = load_manifest()
    specs = {spec.name: spec for spec in manifest.tables}
    paths = {spec.name: spec.path for spec in manifest.tables}
    paths.update({path.stem: path.name for path in SOURCE.glob("*.csv")})
    rows, headers, selected = {}, {}, {}
    for name, relative in paths.items():
        with (SOURCE / relative).open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            headers[name], rows[name] = reader.fieldnames, list(reader)
        selected[name] = set()
    keys = {name: tuple(spec.primary_key) for name, spec in specs.items()}
    keys.update({name: (headers[name][0],) for name in paths if name not in keys})

    def add(name, row):
        selected[name].add(tuple(row[field] for field in keys[name]))

    def chosen(name):
        return [row for row in rows[name] if tuple(row[field] for field in keys[name]) in selected[name]]

    vocabulary = json.loads((LIB / "src/skos/extension_vocabulary.json").read_text())
    for term in vocabulary["admitted_terms"]:
        name = Path(term["source_table"]).stem
        matches = [row for row in rows[name] if row[term["source_key_field"]] == term["source_fixture"]]
        if len(matches) != 1:
            raise ValueError("missing vocabulary source proof: " + term["key"])
        add(name, matches[0])
    for row in rows["lexicon_root_senses"][:2]:
        add("lexicon_root_senses", row)
    for row in rows["affix_degrees"][:2]:
        add("affix_degrees", row)
    profile = json.loads((LIB / "src/skos/composition_profile.json").read_text())
    for term in profile["extension_terms"]:
        for row in [row for row in rows["morpheme_compositions"] if row.get(term["source_field"], "")][:2]:
            add("morpheme_compositions", row)
    for field, values in (("composition_type", profile["admitted_composition_types"]),
                          ("derivation", profile["admitted_derivations"])):
        for value in values:
            add("morpheme_compositions", next(row for row in rows["morpheme_compositions"] if row[field] == value))
    add("source_tables", next(row for row in rows["source_tables"] if row["table_id"] in {"NI-WEB-CH03:T003", "NI-WEB-CH03:T035"}))
    for row in rows["source_tables"]:
        if row["table_id"] in {"NI-WEB-CH03:T003", "NI-WEB-CH03:T035"}:
            add("source_tables", row)
    # A real source-observation debt supplies an explicit held path.
    add("lexicon_root_evidence", next(row for row in rows["lexicon_root_evidence"]
                                      if row["evidence_kind"].startswith("debt_")))

    while True:
        before = sum(map(len, selected.values()))
        for name, spec in specs.items():
            for row in chosen(name):
                for fk in spec.foreign_keys:
                    values = tuple(row[field] for field in fk.fields)
                    if any(not value for value in values):
                        continue
                    for target in rows[fk.target]:
                        if tuple(target[field] for field in fk.target_fields) == values:
                            add(fk.target, target)
        ids = {row[keys[name][0]] for name in ("morphemes_atomic", "morpheme_compositions") for row in chosen(name)}
        for row in rows["source_assertions"]:
            if row["entity_id"] in ids:
                add("source_assertions", row)
        compositions = {row["composition_id"] for row in chosen("morpheme_compositions")}
        for row in rows["composition_components"]:
            if row["composition_id"] in compositions:
                add("composition_components", row)
        for name in ("composition_components", "affix_degrees", "allomorph_rules"):
            for row in chosen(name):
                aliases = {"affix_root_atomic_id": "atomic_id"}
                for field, value in row.items():
                    target_field = aliases.get(field, field)
                    if not value or not target_field.endswith("_id"):
                        continue
                    for target_name, target_keys in keys.items():
                        if target_keys == (target_field,):
                            for target in rows[target_name]:
                                if target[target_field] == value:
                                    add(target_name, target)
        category_codes = {row["category_code"] for row in chosen("morphemes_atomic")}
        for row in rows["grammatical_categories"]:
            if row["category_code"] in category_codes:
                add("grammatical_categories", row)
        count = sum(map(len, selected.values()))
        if count > 500:
            raise ValueError("fixture grew beyond its bounded row budget")
        if count == before:
            break

    TARGET.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, relative in sorted(paths.items()):
        path = TARGET / "csv" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers[name], lineterminator="\n")
            writer.writeheader()
            writer.writerows(chosen(name))
        hashes[relative] = sha(path.read_bytes())

    parent = next(row for row in rows["source_manifest"] if row["source_id"] == "NI-WEB-CH03")
    raw = (LIB / "_raw" / parent["local_name"]).read_bytes()
    if sha(raw) != parent["sha256"]:
        raise ValueError("parent source pin mismatch")
    table = html.fromstring(raw).xpath("//table")[34]
    config_table = html.fromstring(raw).xpath("//table")[2]
    excerpt = b'<!doctype html><html><head><meta charset="utf-8"></head><body>' + etree.tostring(table, encoding="utf-8", method="html") + b"</body></html>\n"
    (TARGET / "source.html").write_bytes(excerpt)
    config_excerpt = etree.tostring(config_table, encoding="utf-8", method="html")
    (TARGET / "configuration.html").write_bytes(config_excerpt)
    locus = next(row for row in rows["source_tables"] if row["table_id"] == "NI-WEB-CH03:T035")
    descriptor = {
        "schema": "bilqis.ithkuil.ingestion-fixture/v1", "version": "1.0.0",
        "fixture_id": "bounded-source-closure-91", "scope": "fixture_only",
        "source_id": "FIXTURE-91-CH03-T035",
        "parent": {"source_id": parent["source_id"], "sha256": parent["sha256"],
                   "url": parent["final_url"], "table_id": locus["table_id"], "table_ordinal": 35,
                   **{field: locus[field] for field in ("section_id", "source_anchor", "source_line")}},
        "excerpt": {"path": "source.html", "sha256": sha(excerpt), "table_ordinal": 1,
                    "matrix_sha256": sha(encoded(table_matrix(table))),
                    "derivation": "lxml-serialized-parent-table/v1"},
        "configuration_excerpt": {"path": "configuration.html", "sha256": sha(config_excerpt),
                                  "parent_table_id": "NI-WEB-CH03:T003"},
        "seed_csv": hashes,
        "seed_provenance": {"repository_commit": "00fc9651fbecdc1b95a05e70eb535d92d0cfeabc",
                            "selection": "unaltered canonical rows plus transitive foreign-key closure; support fixtures for admitted profiles"},
        "claims": {"production_admission": False, "full_new_ithkuil_coverage": False,
                   "curriculum_admission": False},
    }
    (TARGET / "descriptor.json").write_bytes(encoded(descriptor))
    print(json.dumps({"rows": {name: len(chosen(name)) for name in sorted(paths)},
                      "total_rows": sum(map(len, selected.values())), "excerpt_bytes": len(excerpt)}, sort_keys=True))


if __name__ == "__main__":
    main()
