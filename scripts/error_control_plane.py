#!/usr/bin/env python3
"""Generate Bilqis error docs and enforce the unified operator-contract ratchet.

Source-wide opaque error/numeric debt is owned by ``operator_contract_audit``.
This script renders the typed runtime catalog and verifies both that catalog
and the shared pre-migration debt baseline.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "bilqis_mlx"
OPERATIONS = ROOT / "docs" / "operations"
CATALOG_JSON = OPERATIONS / "error_catalog.json"
MANUAL = OPERATIONS / "ERROR_FIELD_MANUAL.md"
BASELINE = ROOT / "docs/evidence/development/operator_contract_baseline.json"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _contains_string_literal(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Constant) and isinstance(child.value, str)
        for child in ast.walk(node)
    )


def _code_hint(node: ast.AST) -> str:
    strings = [
        child.value for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]
    if not strings:
        return ""
    value = strings[0].strip()
    return value.split(":", 1)[0].strip()


def raw_error_sites() -> tuple[dict, ...]:
    """Return grouped production raise sites whose identity contains raw prose."""
    from operator_contract_audit import _repository_python_files

    counts: Counter[tuple[str, str, str, str]] = Counter()
    for path in _repository_python_files(ROOT):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            exception = _call_name(node.exc.func)
            if not exception.endswith("Error") or not node.exc.args:
                continue
            identity = node.exc.args[0]
            if not _contains_string_literal(identity):
                continue
            expression = ast.unparse(identity)
            relative = path.relative_to(ROOT).as_posix()
            counts[(relative, exception, expression, _code_hint(identity))] += 1
    return tuple(
        {
            "path": path,
            "exception": exception,
            "expression": expression,
            "code_hint": code_hint,
            "count": count,
        }
        for (path, exception, expression, code_hint), count in sorted(counts.items())
    )


def _typed_catalog() -> tuple[dict, ...]:
    sys.path.insert(0, str(ROOT))
    from bilqis_mlx.errors import CATALOG

    return tuple({
        "code": spec.code,
        "owner": spec.owner,
        "title": spec.title,
        "message_key": spec.message_key,
        "message_template": spec.message_template,
        "recovery_key": spec.recovery_key,
        "disposition": spec.recovery.disposition,
        "next_action": spec.recovery.next_action,
        "operator_steps": list(spec.recovery.operator_steps),
        "preserve_state": spec.recovery.preserve_state,
        "self_heal_owner": spec.recovery.self_heal_owner,
        "legacy_codes": list(spec.legacy_codes),
    } for spec in CATALOG)


def _operational_catalog() -> tuple[dict, ...]:
    sys.path.insert(0, str(ROOT))
    from bilqis_mlx.operator_vocabulary import OPERATIONAL_TERMS

    return tuple({
        "code": term.code,
        "kind": term.kind.value,
        "owner": term.owner,
        "meaning": term.meaning,
        "next_action": term.next_action,
        "neural_effect": term.neural_effect,
        "aliases": list(term.aliases),
    } for term in OPERATIONAL_TERMS)


def catalog_payload() -> dict:
    raw = raw_error_sites()
    return {
        "schema": "bilqis.error-catalog/v1",
        "typed_errors": list(_typed_catalog()),
        "operational_terms": list(_operational_catalog()),
        "legacy_raw_raise_groups": list(raw),
        "legacy_raw_raise_count": sum(item["count"] for item in raw),
        "legacy_raw_file_count": len({item["path"] for item in raw}),
    }


def _legacy_summary(raw: tuple[dict, ...]) -> tuple[tuple[str, int, tuple[str, ...]], ...]:
    counts: Counter[str] = Counter()
    files: defaultdict[str, set[str]] = defaultdict(set)
    for item in raw:
        code = item["code_hint"] or "<dynamic/raw prose>"
        counts[code] += item["count"]
        files[code].add(item["path"])
    return tuple(
        (code, counts[code], tuple(sorted(files[code])))
        for code in sorted(counts)
    )


def _typed_manual_sections(typed):
    lines = []
    for item in typed:
        lines.extend([
            "### `" + item["code"] + "`",
            "",
            item["title"] + ".",
            "",
            "Owner: `" + item["owner"] + "`",
            "Disposition: `" + item["disposition"] + "`",
            "Self-heal owner: `" + (item["self_heal_owner"] or "none") + "`",
            "",
            "Message: " + item["message_template"],
            "",
            "Recovery: " + item["next_action"],
        ])
        if item["operator_steps"]:
            lines.extend(["", "Operator steps:"])
            lines.extend(
                str(index) + ". " + step
                for index, step in enumerate(item["operator_steps"], 1)
            )
        if item["legacy_codes"]:
            lines.extend([
                "",
                "Legacy aliases: " + ", ".join(
                    "`" + code + "`" for code in item["legacy_codes"]),
            ])
        lines.append("")

    return lines


def render_manual(payload: dict) -> str:
    typed = payload["typed_errors"]
    operational = payload["operational_terms"]
    raw = tuple(payload["legacy_raw_raise_groups"])
    lines = [
        "# Bilqis Error Field Manual",
        "",
        "> Generated by `scripts/error_control_plane.py`. Do not edit by hand.",
        "",
        "The runtime error catalog is the authority for new failures. Raw string "
        "exceptions are legacy migration debt and may only decrease.",
        "",
        "## Operator procedure",
        "",
        "1. Read the dotted error code. It identifies the owning domain and invariant.",
        "2. Read `WHAT HAPPENED` and `DETAILS`. They contain the preserved failure context.",
        "3. Follow the named self-heal owner before taking manual action.",
        "4. Preserve checkpoint and optimizer custody when the report says to preserve state.",
        "5. Run `python3 -m bilqis_mlx.cli explain CODE` for any cataloged term.",
        "",
        "## Typed catalog",
        "",
    ]
    lines.extend(_typed_manual_sections(typed))

    lines.extend([
        "## Operational signals and blockers",
        "",
        "These terms are not exceptions. They describe a controlled stop, handoff, or gate.",
        "",
    ])
    for item in operational:
        lines.extend([
            "### `" + item["code"] + "`",
            "",
            "Kind: `" + item["kind"] + "`",
            "Owner: `" + item["owner"] + "`",
            "",
            "Meaning: " + item["meaning"],
            "",
            "Neural effect: " + item["neural_effect"],
            "",
            "Next action: " + item["next_action"],
        ])
        if item["aliases"]:
            lines.extend([
                "",
                "Aliases/events: " + ", ".join(
                    "`" + code + "`" for code in item["aliases"]),
            ])
        lines.append("")

    lines.extend([
        "## Legacy raw-string debt",
        "",
        "Current production scan: **" + str(payload["legacy_raw_raise_count"]) +
        "** raw raises across **" + str(payload["legacy_raw_file_count"]) +
        "** files. The baseline gate permits only reduction.",
        "",
        "| Legacy code/prefix | Raises | Files |",
        "| --- | ---: | --- |",
    ])
    for code, count, files in _legacy_summary(raw):
        visible_files = ", ".join("`" + path + "`" for path in files[:4])
        if len(files) > 4:
            visible_files += ", plus " + str(len(files) - 4) + " more"
        lines.append("| `" + code.replace("|", "\\|") + "` | " +
                     str(count) + " | " + visible_files + " |")
    lines.extend([
        "",
        "Full source expressions and grouped counts are in `docs/operations/error_catalog.json`.",
        "",
    ])
    return "\n".join(lines)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_docs() -> None:
    OPERATIONS.mkdir(parents=True, exist_ok=True)
    payload = catalog_payload()
    CATALOG_JSON.write_text(_canonical(payload), encoding="utf-8")
    MANUAL.write_text(render_manual(payload), encoding="utf-8")


def check() -> int:
    if not BASELINE.is_file():
        print("ERROR_CONTROL_BASELINE_MISSING", file=sys.stderr)
        return 2
    from operator_contract_audit import (
        _read_baseline, debt_counter, new_debt, scan_tree,
    )
    source_report = scan_tree(ROOT)
    introduced = new_debt(
        debt_counter(source_report.debt), _read_baseline(BASELINE))
    if introduced:
        print("NEW_OPAQUE_OPERATOR_CONTRACT_DEBT_FORBIDDEN", file=sys.stderr)
        for item in introduced[:30]:
            print(" | ".join(item), file=sys.stderr)
        return 1
    payload = catalog_payload()
    expected_json = _canonical(payload)
    expected_manual = render_manual(payload)
    if (not CATALOG_JSON.is_file() or
            CATALOG_JSON.read_text(encoding="utf-8") != expected_json or
            not MANUAL.is_file() or
            MANUAL.read_text(encoding="utf-8") != expected_manual):
        print("ERROR_FIELD_MANUAL_STALE: run scripts/error_control_plane.py --write-docs",
              file=sys.stderr)
        return 1
    print(
        "ERROR_CONTROL_PLANE_OK | raw error sites " +
        str(payload["legacy_raw_raise_count"]) +
        " | opaque error/numeric debt " + str(len(source_report.debt)) +
        " | new debt 0"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write-docs", action="store_true")
    actions.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write_docs:
        write_docs()
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
