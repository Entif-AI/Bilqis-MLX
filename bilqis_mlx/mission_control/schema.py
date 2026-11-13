"""JSON Schema projection generated from the typed CP02 record family."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import types
from typing import get_args, get_origin, get_type_hints, Union

from .model import WireRecord


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BUNDLE_VERSION = "bilqis.bamf.mission-control.schema-bundle/v1"
_VARIADIC_TUPLE_ARITY = 2


def _schema_for_type(expected):
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (types.UnionType, Union):
        return {"anyOf": [_schema_for_type(option) for option in args]}
    if origin is tuple:
        if len(args) == _VARIADIC_TUPLE_ARITY and args[1] is Ellipsis:
            return {"type": "array", "items": _schema_for_type(args[0])}
        return {
            "type": "array",
            "prefixItems": [_schema_for_type(option) for option in args],
            "minItems": len(args),
            "maxItems": len(args),
        }
    if expected is type(None):
        return {"type": "null"}
    if isinstance(expected, type) and issubclass(expected, Enum):
        return {"type": "string", "enum": [item.value for item in expected]}
    if isinstance(expected, type) and is_dataclass(expected):
        hints = get_type_hints(expected)
        properties = {
            field.name: _schema_for_type(hints[field.name])
            for field in fields(expected)
        }
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }
    if expected is str:
        return {"type": "string"}
    if expected is int:
        return {"type": "integer"}
    if expected is float:
        return {"type": "number"}
    if expected is bool:
        return {"type": "boolean"}
    raise TypeError


def record_schema(record_type: type[WireRecord]) -> dict:
    if not isinstance(record_type, type) or not issubclass(record_type, WireRecord):
        raise TypeError
    body = _schema_for_type(record_type)
    properties = {
        "schema_version": {"type": "string", "const": record_type.SCHEMA},
        **body["properties"],
    }
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": record_type.SCHEMA,
        "title": record_type.__name__,
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def schema_bundle() -> dict:
    from .registry import ALL_RECORD_TYPES
    return {
        "schema_version": SCHEMA_BUNDLE_VERSION,
        "records": {
            record_type.SCHEMA: record_schema(record_type)
            for record_type in ALL_RECORD_TYPES
        },
    }
