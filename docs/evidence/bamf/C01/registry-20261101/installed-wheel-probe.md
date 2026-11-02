# Installed source-frame interface probe

The five structural repairs were built from git archive commit
`4ab0752d9bdafeee25c486bb0ef5979872d48281` in a fresh temporary source tree. A separate build environment
contained setuptools/wheel; the portable runtime dependency environment was not
changed. Pip built with `--no-deps --no-build-isolation` and installed the wheel
into a fresh `--target` directory.

Wheel: `bilqis_mlx_private-0.5.0-py3-none-any.whl`; SHA256 `6452e4d52d282e61eaaedf34d796cdc48ef4397afadaef0f06848effc6456913`.
The installed selection passed **93/93**, zero failures/errors/skips, from `/tmp`
using `/tmp/c524-venv/bin/python -I`. Every loaded `bilqis_mlx` module and namespace
path was verified under that installed target. Both real source asset variables
were supplied, as described in the frame-schema and released-schema evidence.

The selection excludes 70 repository-only BAMF script tests and the one IO fixture
that reads the source checkout's vendor tree. All 71 exclusions pass in the full
164-case source selection; they are not represented as installed-wheel passes.
The installed probe still includes real source-pinned schema families and the
real Atlas concept/type-authority witness.

Save the following as a probe file and run it with the clean installed target:

```sh
python -I /path/to/probe.py /path/to/installed-target
```

Use the same runtime dependencies as the portable source suite. This is a finite
verification recipe, not learner, optimizer, training or source-admission authority.

```python
"""Verify installed semantic tests and module provenance without source imports."""
import importlib
import inspect
from pathlib import Path
import sys
import unittest

installed = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(installed))
packages = (
    'frame_compiler', 'partial_visible_forest', 'released_schemas',
    'frame_schema', 'frame_codec', 'source_atom_binding',
)
suite = unittest.TestSuite()
excluded = []
for package in packages:
    name = 'bilqis_mlx.semantics.tests.' + package
    module = importlib.import_module(name)
    folder = Path(next(iter(module.__path__)))
    for path in sorted(folder.glob('test_*.py')):
        test_module = importlib.import_module(name + '.' + path.stem)
        for value in vars(test_module).values():
            if (not inspect.isclass(value) or not issubclass(value, unittest.TestCase)
                    or value.__module__ != test_module.__name__):
                continue
            for test in unittest.defaultTestLoader.loadTestsFromTestCase(value):
                if test.id().endswith(
                        '.test_real_registered_a_source_schema_can_be_published_and_verified'):
                    excluded.append(test.id())
                else:
                    suite.addTest(test)
assert suite.countTestCases() == 93, suite.countTestCases()
assert len(excluded) == 1, excluded
result = unittest.TextTestRunner(verbosity=2).run(suite)
wrong = []
for name, module in tuple(sys.modules.items()):
    if name != 'bilqis_mlx' and not name.startswith('bilqis_mlx.'):
        continue
    filename = getattr(module, '__file__', None)
    if filename and not Path(filename).resolve().is_relative_to(installed):
        wrong.append((name, filename))
    for directory in getattr(module, '__path__', ()):
        if not Path(directory).resolve().is_relative_to(installed):
            wrong.append((name, directory))
assert not wrong, wrong
assert not result.skipped, result.skipped
print('INSTALLED_WHEEL_MODULE_ORIGINS_OK')
print('REPOSITORY_ONLY_FIXTURE_EXCLUDED', *excluded)
print('INSTALLED_TEST_TOTALS', result.testsRun,
      len(result.failures), len(result.errors), len(result.skipped))
raise SystemExit(0 if result.wasSuccessful() else 1)
```
