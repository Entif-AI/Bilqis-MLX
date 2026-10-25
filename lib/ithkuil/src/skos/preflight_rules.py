"""Source-structural semantic invariants for issue #37 preflight."""

from __future__ import annotations

from .preflight_io import FrozenRow, LoadedInput, ValidationFinding, finding
from .preflight_manifest import InputManifest


def _key_text(values: tuple[str, ...]) -> str:
    return "|".join(values)


def _validate_sense_coordinates(loaded: LoadedInput) -> list[ValidationFinding]:
    findings = []
    rules = (
        (
            "root_senses",
            "sense_id",
            {"", "STEM 1", "STEM 2", "STEM 3"},
            {"", "BSC", "CTE", "CSV", "OBJ"},
        ),
        (
            "lexicon_root_senses",
            "lexicon_sense_id",
            {"", "STEM 1", "STEM 2", "STEM 3", "STEMS 1-3"},
            {"BSC", "CTE", "CSV", "OBJ"},
        ),
    )
    for table_name, key_field, allowed_stems, allowed_specs in rules:
        for row in loaded.table(table_name).rows:
            if row["stem"].upper() not in allowed_stems:
                findings.append(
                    finding(
                        "INVALID_ENUM_STATE",
                        table_name,
                        key=row[key_field],
                        field="stem",
                        locus=f"row={row.fingerprint}",
                        details=(f"value={row['stem']!r}",),
                    )
                )
            if row["specification"].upper() not in allowed_specs:
                findings.append(
                    finding(
                        "INVALID_ENUM_STATE",
                        table_name,
                        key=row[key_field],
                        field="specification",
                        locus=f"row={row.fingerprint}",
                        details=(f"value={row['specification']!r}",),
                    )
                )
    return findings


def validate_semantic_invariants(
    loaded: LoadedInput, manifest: InputManifest
) -> list[ValidationFinding]:
    """Validate only source-structural invariants needed before #38."""
    findings = _validate_sense_coordinates(loaded)
    assertions = loaded.table("source_assertions")
    asserted: dict[str, set[str]] = {}
    for row in assertions.rows:
        asserted.setdefault(row["entity_kind"], set()).add(row["entity_id"])

    for invariant in manifest.semantic_invariants:
        config = invariant.config
        if invariant.name.endswith("_source_assertion_coverage"):
            table = loaded.table(config["table"])
            for row in table.rows:
                value = row[config["key_field"]]
                if value not in asserted.get(config["assertion_kind"], set()):
                    findings.append(
                        finding(
                            config["reason_code"],
                            config["table"],
                            key=value,
                            field=config["key_field"],
                            locus=f"row={row.fingerprint}",
                        )
                    )
        elif invariant.name == "atomic_semantic_key_label_consistency":
            table = loaded.table(config["table"])
            groups: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
            for row in table.rows:
                key = tuple(row[field] for field in config["key_fields"])
                value = tuple(row[field] for field in config["value_fields"])
                groups.setdefault(key, set()).add(value)
            for key, values in groups.items():
                if len(values) > 1:
                    findings.append(
                        finding(
                            config["reason_code"],
                            config["table"],
                            key=_key_text(key),
                            field=",".join(config["value_fields"]),
                            locus="semantic-key",
                            details=tuple(repr(value) for value in sorted(values)),
                        )
                    )
        elif invariant.name == "lexicon_child_parent_binding":
            parents = {
                row[config["parent_key"]]: row
                for row in loaded.table(config["parent"]).rows
            }
            locus_fields = config.get("locus_fields", [])
            source_loci = {
                tuple(row[field] for field in locus_fields)
                for row in parents.values()
            }
            for child_name in config["children"]:
                for row in loaded.table(child_name).rows:
                    parent = parents.get(row[config["parent_key"]])
                    if parent is None:
                        continue
                    if tuple(row[field] for field in locus_fields) not in source_loci:
                        findings.append(finding(
                            config["reason_code"], child_name,
                            key=row[config["parent_key"]], field=",".join(locus_fields),
                            locus=f"row={row.fingerprint}",
                            details=("observation does not match a declared source locus",),
                        ))
                    for field in config["equal_fields"]:
                        if row[field] != parent[field]:
                            findings.append(
                                finding(
                                    config["reason_code"],
                                    child_name,
                                    key=row[config["parent_key"]],
                                    field=field,
                                    locus=f"row={row.fingerprint}",
                                    details=(
                                        f"child={row[field]!r}",
                                        f"parent={parent[field]!r}",
                                    ),
                                )
                            )
    return findings
