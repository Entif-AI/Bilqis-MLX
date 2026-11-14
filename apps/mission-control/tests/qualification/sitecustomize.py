"""Bound GUI05 qualification when MLX is requested, without importing it eagerly."""
import importlib.abc
import importlib.machinery
import os
import sys


class _BoundedMlxLoader:
    def __init__(self, loader):
        self.loader = loader

    def create_module(self, spec):
        return self.loader.create_module(spec)

    def exec_module(self, module):
        self.loader.exec_module(module)
        module.set_memory_limit(1024**3)
        module.set_cache_limit(0)


class _BoundedMlxFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != "mlx.core":
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is not None:
            spec.loader = _BoundedMlxLoader(spec.loader)
        return spec


if os.environ.get("BILQIS_GUI05_BOUNDED_TEST") == "1":
    sys.meta_path.insert(0, _BoundedMlxFinder())
