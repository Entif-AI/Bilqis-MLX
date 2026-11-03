"""Restore public metadata without replacing relocated semantic contract objects."""
from types import FunctionType
from typing import TypeVar


_Export = TypeVar('_Export', bound=type | FunctionType)


def _restore_function(function: FunctionType, module_name: str) -> None:
    origin = function.__module__
    while isinstance(function, FunctionType) and function.__module__ == origin:
        function.__module__ = module_name
        function = getattr(function, '__wrapped__', None)


def restore_public_module(value: _Export, module_name: str) -> _Export:
    """Preserve class-owned descriptors and wrapped methods, leaving foreign functions alone."""
    if isinstance(value, FunctionType):
        _restore_function(value, module_name)
        return value
    origin = value.__module__
    value.__module__ = module_name
    prefix = value.__qualname__ + '.'
    for member in vars(value).values():
        if isinstance(member, (classmethod, staticmethod)):
            functions = (member.__func__,)
        elif isinstance(member, property):
            functions = (member.fget, member.fset, member.fdel)
        else:
            functions = (member,)
        for function in functions:
            if (isinstance(function, FunctionType) and function.__module__ == origin
                    and function.__qualname__.startswith(prefix)):
                _restore_function(function, module_name)
    return value
