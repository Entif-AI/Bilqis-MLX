"""Prevent this physical directory from creating alternate module names.

Runtime searches this directory for its established module names. An empty
subpackage search path prevents the same files loading again under this name.
"""

__path__ = []
