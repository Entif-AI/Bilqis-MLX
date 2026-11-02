# Installed source-frame interface probe

The refreshed candidate, including the accepted unified codec and #731 repair,
was built from git archive commit
`7c8b75a418e726060945f2b9cbe296063b7d9ee4` in a fresh temporary source tree. A separate build environment
contained setuptools/wheel; the portable runtime dependency environment was not
changed. Pip built with `--no-deps --no-build-isolation` and installed the wheel
into a fresh `--target` directory.

Wheel: `bilqis_mlx_private-0.5.0-py3-none-any.whl`; SHA256 `51ae463fa8470dc29bb9d1671ecce564451a31b53f754f1337a5cf96f6c93b51`.
The installed selection passed **116/116**, zero failures/errors/skips, from `/tmp`
using `/tmp/c524-venv/bin/python -I`. Every loaded `bilqis_mlx` module and namespace
path was verified under that installed target. Both real source asset variables
were supplied, as described in the frame-schema and released-schema evidence.

The selection excludes 70 repository-only BAMF script tests and the one IO fixture
that reads the source checkout's vendor tree. All 71 exclusions pass in the full
187-case source selection; they are not represented as installed-wheel passes.
The probe adds unified's 22 codec cases and the #731 annotation regression to
the historical 93-case installed selection. It includes real source-pinned schema families and the
real Atlas concept/type-authority witness.

## Rebuild inputs and the installed target

Run from a Bilqis checkout containing the pinned source commit. If the commit is
missing, fetch the published parent candidate with
`git fetch origin pull/694/head`, then retry the explicit `git cat-file` check below.
The source inputs are the tracked `lib/ithkuil/_data/csv` records. No separately
copied machine-local fixture is required. The conformance owner rebuilds the source
bundle; the Atlas rebuilder independently requires its existing release/bundle pins.
These are disposable test inputs, not new semantic admission. See the originating
[source-custody record](../../A05.5/source-owned-candidate-v2.md#source-custody).

Executed environment: macOS, Python 3.14.4. The project declares Python >=3.11;
other interpreters/platforms have not been exercised by this receipt. Package
versions below describe the tested environment, not a claim of minimal dependencies.
A fresh setup requires Python with venv, Git/tar and package-index access. It installs
`lib/ithkuil/requirements-semantic.txt` (rdflib/pyshacl pins), NumPy and cryptography
in one runtime environment, and setuptools/wheel in a separate builder. It does not
use system site packages or the author's earlier temporary environments.

Save the Python block below as `/tmp/c01-frame-probe.py` before running this shell
block. That is the entire probe: no unpublished helper is needed.

```sh
set -eu
C01_PROBE=/tmp/c01-frame-probe.py
C01_SOURCE_SHA=7c8b75a418e726060945f2b9cbe296063b7d9ee4
git cat-file -e "$C01_SOURCE_SHA^{commit}"
C01_WORK=$(mktemp -d "${TMPDIR:-/tmp}/c01-reproduce.XXXXXX")
mkdir "$C01_WORK/source"
git archive "$C01_SOURCE_SHA" | tar -x -C "$C01_WORK/source"
python3 -m venv "$C01_WORK/runtime"
C01_PY="$C01_WORK/runtime/bin/python"
"$C01_PY" -m pip install \
  -r "$C01_WORK/source/lib/ithkuil/requirements-semantic.txt" \
  numpy==2.5.4 cryptography==50.0.2
cd "$C01_WORK/source"
"$C01_PY" -B -m lib.ithkuil.src.skos.conformance \
  --input-root lib/ithkuil/_data/csv --output-root "$C01_WORK/corpus"
export BILQIS_ATLAS_REAL_CORPUS="$C01_WORK/corpus/f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec"
test -d "$BILQIS_ATLAS_REAL_CORPUS"
"$C01_PY" -B -m scripts.bamf.rebuild_atlas_artifact \
  --source-bundle "$BILQIS_ATLAS_REAL_CORPUS" --output-root "$C01_WORK/atlas"
export BILQIS_ATLAS_REAL_ARTIFACT="$C01_WORK/atlas/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
test -d "$BILQIS_ATLAS_REAL_ARTIFACT"
python3 -m venv "$C01_WORK/builder"
"$C01_WORK/builder/bin/python" -m pip install setuptools==84.2.1 wheel==0.48.0
"$C01_WORK/builder/bin/python" -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir "$C01_WORK/wheels" "$C01_WORK/source"
"$C01_PY" -m pip install --no-deps --target "$C01_WORK/installed" \
  "$C01_WORK/wheels/bilqis_mlx_private-0.5.0-py3-none-any.whl"
cp "$C01_PROBE" "$C01_WORK/probe.py"
cd /tmp
"$C01_PY" -I "$C01_WORK/probe.py" "$C01_WORK/installed"
```

The two output directories must have exactly the names above. A different digest
or an unsuccessful source gate is a failed reproduction, not permission to replace
the expected pins. The wheel SHA above identifies one observed build; wheel archive
timestamps may differ on regeneration. Acceptance checks its pinned source, executed
suite and installed origins, not byte-for-byte reproducibility of the wheel archive.

To reproduce the 187-case source proof, keep these exported variables and run the
[full source selection](current-unified-refresh.md#defect-and-exact-source-proof)
from `$C01_WORK/source` using `$C01_PY` instead of `python`. This source checkout
also retains the vendor-only fixture intentionally excluded from the installed
selection. Do not run that selection in the installed target.

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
suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
    'bilqis_mlx.semantics.tests.test_frame_codec'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
    'bilqis_mlx.semantics.frame_codec_parts.tests.test_schema_tags'))
assert suite.countTestCases() == 116, suite.countTestCases()
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

Historical receipt: `4ab0752d` passed 93/93 in the earlier installed selection.
The current 116-case result does not retroactively change that historical proof.

## Independent fixture rebuild receipt — #733

The documented acquisition/build commands were executed in newly created runtime
and builder environments against git-archive source `7c8b75a4`. The public tracked
CSV records rebuilt the exact corpus and Atlas bundle IDs above. All four source
conformance gates passed; source coverage remains explicitly partial. No older
local fixture directory was supplied. The full source selection then passed
187/187, zero skips, and the fresh installed target passed 116/116, zero skips,
with every Bilqis origin inside that target. The probe copied from this document
has the same complete AST as the executed probe.

This fresh recipe build produced wheel SHA256 `2f84f7e8fb1b1e7ddca04ab14896facffecb1f105aa404a55e07857c5d477ae1`.
It is a separate observed archive from the earlier build at the top of this file.
The reproduction does not require equal wheel timestamps or archive bytes.
An ordinary independent read of both recipe documents found no actionable issue;
that reader did not execute the commands. Whole-candidate EGM remains separate.
