"""Immutable compiler-input manifest model for issue #37."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath

from .errors import ProfileError


DEFAULT_MANIFEST_PATH = Path(__file__).with_name("compiler_input_manifest.json")
SUPPORTED_MANIFEST_VERSIONS = frozenset({"bilqis.skos.compiler-input/v1"})
SUPPORTED_SEMANTIC_INVARIANTS = frozenset(
    {
        "atomic_source_assertion_coverage",
        "composition_source_assertion_coverage",
        "atomic_semantic_key_label_consistency",
        "lexicon_child_parent_binding",
    }
)


@dataclass(frozen=True)
class ForeignKeySpec:
    fields: tuple[str, ...]
    target: str
    target_fields: tuple[str, ...]
    optional_if_any_blank: bool = False


@dataclass(frozen=True)
class TableSpec:
    name: str
    path: str
    role: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    required_nonblank: tuple[str, ...]
    foreign_keys: tuple[ForeignKeySpec, ...]
    enums: tuple[tuple[str, tuple[str, ...]], ...]

    def enum_values(self, field: str) -> frozenset[str]:
        return frozenset(dict(self.enums).get(field, ()))


@dataclass(frozen=True)
class ConditionalForeignKeySpec:
    table: str
    selector_field: str
    source_field: str
    targets: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class SourceBindingSpec:
    table: str
    source_field: str
    url_field: str


@dataclass(frozen=True)
class SemanticInvariantSpec:
    name: str
    config_json: str

    @property
    def config(self) -> dict:
        return json.loads(self.config_json)


@dataclass(frozen=True)
class InputManifest:
    version: str
    description: str
    reason_codes: tuple[str, ...]
    tables: tuple[TableSpec, ...]
    conditional_foreign_keys: tuple[ConditionalForeignKeySpec, ...]
    source_bindings: tuple[SourceBindingSpec, ...]
    semantic_invariants: tuple[SemanticInvariantSpec, ...]
    deferred_non_core: tuple[tuple[str, str], ...]

    def table(self, name: str) -> TableSpec:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(name)

def _manifest_error(*details: str) -> None:
    raise ProfileError("INVALID_COMPILER_INPUT_MANIFEST", *details)

def _require_fields(columns: set[str], fields: list[str], label: str) -> None:
    missing = sorted(set(fields) - columns)
    if missing:
        _manifest_error(label, "missing=" + ",".join(missing))

def _validate_raw_manifest(raw: dict) -> None:
    if raw.get("version") not in SUPPORTED_MANIFEST_VERSIONS:
        _manifest_error("unsupported_version", repr(raw.get("version")))
    tables = raw.get("tables")
    if not isinstance(tables, list) or not tables:
        _manifest_error("tables_missing")
    names = [table.get("name") for table in tables]
    paths = [table.get("path") for table in tables]
    if len(names) != len(set(names)):
        _manifest_error("duplicate_table_name")
    if len(paths) != len(set(paths)):
        _manifest_error("duplicate_table_path")
    by_name = {}
    for table in tables:
        name = table.get("name")
        path = table.get("path")
        columns = table.get("columns")
        if not isinstance(name, str) or not name:
            _manifest_error("invalid_table_name")
        if not isinstance(path, str) or not path:
            _manifest_error("invalid_table_path", str(name))
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            _manifest_error("unsafe_table_path", str(name), path)
        if not isinstance(columns, list) or not columns:
            _manifest_error("columns_missing", str(name))
        if len(columns) != len(set(columns)):
            _manifest_error("duplicate_column_name", str(name))
        column_set = set(columns)
        primary_key = table.get("primary_key", [])
        if not primary_key:
            _manifest_error("primary_key_missing", str(name))
        _require_fields(column_set, primary_key, f"{name}:primary_key")
        _require_fields(
            column_set, table.get("required_nonblank", []), f"{name}:required_nonblank"
        )
        _require_fields(column_set, list(table.get("enums", {})), f"{name}:enums")
        by_name[name] = table
    for table in tables:
        source_columns = set(table["columns"])
        for foreign_key in table.get("foreign_keys", []):
            fields = foreign_key.get("fields", [])
            target_fields = foreign_key.get("target_fields", [])
            target_name = foreign_key.get("target")
            if not fields or len(fields) != len(target_fields):
                _manifest_error("foreign_key_arity", table["name"], str(target_name))
            _require_fields(source_columns, fields, f"{table['name']}:foreign_key")
            if target_name not in by_name:
                _manifest_error("foreign_key_target_table", table["name"], str(target_name))
            _require_fields(
                set(by_name[target_name]["columns"]),
                target_fields,
                f"{table['name']}:foreign_key_target",
            )
    for conditional in raw.get("conditional_foreign_keys", []):
        table_name = conditional.get("table")
        if table_name not in by_name:
            _manifest_error("conditional_fk_table", str(table_name))
        columns = set(by_name[table_name]["columns"])
        _require_fields(
            columns,
            [conditional.get("selector_field"), conditional.get("source_field")],
            f"{table_name}:conditional_fk",
        )
        targets = conditional.get("targets")
        if not isinstance(targets, dict) or not targets:
            _manifest_error("conditional_fk_targets", str(table_name))
        enum_values = set(by_name[table_name].get("enums", {}).get(conditional["selector_field"], []))
        if set(targets) != enum_values:
            _manifest_error("conditional_fk_selector_coverage", str(table_name))
        for selector, target in targets.items():
            target_name = target.get("table")
            target_field = target.get("field")
            if target_name not in by_name:
                _manifest_error("conditional_fk_target_table", selector, str(target_name))
            _require_fields(
                set(by_name[target_name]["columns"]),
                [target_field],
                f"{table_name}:conditional_fk_target",
            )
    for binding in raw.get("source_bindings", []):
        table_name = binding.get("table")
        if table_name not in by_name:
            _manifest_error("source_binding_table", str(table_name))
        _require_fields(
            set(by_name[table_name]["columns"]),
            [binding.get("source_field"), binding.get("url_field")],
            f"{table_name}:source_binding",
        )
    invariants = raw.get("semantic_invariants", [])
    names = [item.get("name") for item in invariants]
    unknown = sorted(set(names) - SUPPORTED_SEMANTIC_INVARIANTS)
    if unknown:
        _manifest_error("unsupported_semantic_invariant", ",".join(unknown))
    for item in invariants:
        name = item["name"]
        if name.endswith("_source_assertion_coverage"):
            table_name = item.get("table")
            if table_name not in by_name:
                _manifest_error("semantic_invariant_table", name, str(table_name))
            _require_fields(
                set(by_name[table_name]["columns"]),
                [item.get("key_field")],
                f"{name}:key_field",
            )
        elif name == "atomic_semantic_key_label_consistency":
            table_name = item.get("table")
            if table_name not in by_name:
                _manifest_error("semantic_invariant_table", name, str(table_name))
            columns = set(by_name[table_name]["columns"])
            _require_fields(columns, item.get("key_fields", []), f"{name}:key_fields")
            _require_fields(columns, item.get("value_fields", []), f"{name}:value_fields")
            _require_fields(
                columns,
                item.get("ignored_realization_fields", []),
                f"{name}:ignored_fields",
            )
        elif name == "lexicon_child_parent_binding":
            parent = item.get("parent")
            children = item.get("children", [])
            parent_key = item.get("parent_key")
            if parent not in by_name or not children:
                _manifest_error("semantic_invariant_table", name)
            _require_fields(
                set(by_name[parent]["columns"]),
                [parent_key, *item.get("equal_fields", []), *item.get("locus_fields", [])],
                f"{name}:parent_fields",
            )
            for child in children:
                if child not in by_name:
                    _manifest_error("semantic_invariant_table", name, str(child))
                _require_fields(
                    set(by_name[child]["columns"]),
                    [parent_key, *item.get("equal_fields", []), *item.get("locus_fields", [])],
                    f"{name}:child_fields",
                )
    if len(raw.get("reason_codes", [])) != len(set(raw.get("reason_codes", []))):
        _manifest_error("duplicate_reason_code")

def load_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> InputManifest:
    """Load the versioned manifest. This is configuration I/O, not corpus I/O."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _manifest_error(type(error).__name__)
    if not isinstance(raw, dict):
        _manifest_error("root_not_object")
    _validate_raw_manifest(raw)
    tables = []
    for table in raw["tables"]:
        tables.append(
            TableSpec(
                name=table["name"],
                path=table["path"],
                role=table["role"],
                columns=tuple(table["columns"]),
                primary_key=tuple(table["primary_key"]),
                required_nonblank=tuple(table["required_nonblank"]),
                foreign_keys=tuple(
                    ForeignKeySpec(
                        fields=tuple(fk["fields"]),
                        target=fk["target"],
                        target_fields=tuple(fk["target_fields"]),
                        optional_if_any_blank=fk.get("optional_if_any_blank", False),
                    )
                    for fk in table["foreign_keys"]
                ),
                enums=tuple(
                    (field, tuple(values))
                    for field, values in sorted(table["enums"].items())
                ),
            )
        )
    conditional = tuple(
        ConditionalForeignKeySpec(
            table=item["table"],
            selector_field=item["selector_field"],
            source_field=item["source_field"],
            targets=tuple(
                (selector, target["table"], target["field"])
                for selector, target in sorted(item["targets"].items())
            ),
        )
        for item in raw["conditional_foreign_keys"]
    )
    bindings = tuple(
        SourceBindingSpec(
            table=item["table"],
            source_field=item["source_field"],
            url_field=item["url_field"],
        )
        for item in raw["source_bindings"]
    )
    invariants = tuple(
        SemanticInvariantSpec(
            name=item["name"],
            config_json=json.dumps(item, ensure_ascii=False, sort_keys=True),
        )
        for item in raw["semantic_invariants"]
    )
    return InputManifest(
        version=raw["version"],
        description=raw["description"],
        reason_codes=tuple(raw["reason_codes"]),
        tables=tuple(tables),
        conditional_foreign_keys=conditional,
        source_bindings=bindings,
        semantic_invariants=invariants,
        deferred_non_core=tuple(sorted(raw["deferred_non_core"].items())),
    )
