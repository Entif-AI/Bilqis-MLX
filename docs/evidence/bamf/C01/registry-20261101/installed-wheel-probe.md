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

## Required fixture access

This recipe verifies supplied fixtures; it does not independently regenerate them.
Before running it, obtain read access to both complete, previously verified bundles
from the source-fixture custodian:

- `BILQIS_ATLAS_REAL_ARTIFACT`: the A01 Atlas artifact directory named
  `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`,
  including `manifest.json`, `atlas.json`, `concepts.jsonl`, `relations.jsonl`
  and `held.jsonl`.
- `BILQIS_ATLAS_REAL_CORPUS`: the conformance directory named
  `f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`,
  including its manifest, canonical/admitted RDF, coverage, source rows and gate
  receipts. Supply the whole bundle, not just the listed files.

The repository does not provide a public download or an established end-to-end
regeneration recipe for these exact bytes. The machine-local paths in older
receipts are historical locations, not distribution endpoints. Without separately
supplied access this no-skip proof is unavailable. Do not substitute a synthetic
bundle, rename another directory to the expected digest, or count skipped tests
as reproduction. The source tests re-enter the pinned Atlas/schema authorities;
the directory names alone are not verification.

## Fresh archive, environments and wheel

Prerequisites: a clone containing source commit
`7c8b75a418e726060945f2b9cbe296063b7d9ee4`, Python 3.12 or newer with `venv`,
Git, tar, and package-index access. Run from this repository root after exporting
both fixture variables as absolute directory paths. Fixtures remain read-only.
The archive is the historical tested source commit, not an assertion that a later
parent candidate passes its whole-candidate gates.

```sh
set -eu
: "${BILQIS_ATLAS_REAL_ARTIFACT:?Supply the verified A01 artifact directory}"
: "${BILQIS_ATLAS_REAL_CORPUS:?Supply the verified conformance directory}"
test -f "$BILQIS_ATLAS_REAL_ARTIFACT/manifest.json"
test -f "$BILQIS_ATLAS_REAL_CORPUS/manifest.json"
export BILQIS_ATLAS_REAL_ARTIFACT BILQIS_ATLAS_REAL_CORPUS
proof_repo=$(git rev-parse --show-toplevel)
proof_commit=7c8b75a418e726060945f2b9cbe296063b7d9ee4
proof_root=$(mktemp -d "${TMPDIR:-/tmp}/c01-proof.XXXXXX")
mkdir "$proof_root/source" "$proof_root/wheels" "$proof_root/installed"
git -C "$proof_repo" archive "$proof_commit" > "$proof_root/source.tar"
tar -xf "$proof_root/source.tar" -C "$proof_root/source"
python3 -m venv "$proof_root/runtime"
python3 -m venv "$proof_root/build"
"$proof_root/runtime/bin/python" -m pip install \
  cryptography==50.0.2 numpy==2.5.4 rdflib==7.6.0 pyshacl==0.40.1
"$proof_root/build/bin/python" -m pip install setuptools wheel
"$proof_root/runtime/bin/python" -m pip freeze > "$proof_root/runtime-freeze.txt"
"$proof_root/build/bin/python" -m pip freeze > "$proof_root/build-freeze.txt"
"$proof_root/runtime/bin/python" --version > "$proof_root/python-version.txt"
"$proof_root/build/bin/python" -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir "$proof_root/wheels" "$proof_root/source"
"$proof_root/runtime/bin/python" -m pip install --no-deps \
  --target "$proof_root/installed" "$proof_root"/wheels/*.whl
"$proof_root/runtime/bin/python" - "$proof_root" "$proof_commit" <<'PY'
import hashlib
from pathlib import Path
import sys
root = Path(sys.argv[1])
wheels = list((root / 'wheels').glob('*.whl'))
assert len(wheels) == 1, wheels
receipt = f'SOURCE_COMMIT {sys.argv[2]}\nWHEEL_SHA256 {hashlib.sha256(wheels[0].read_bytes()).hexdigest()}\n'
(root / 'build-receipt.txt').write_text(receipt)
print(receipt, end='')
PY
```

The runtime pins above are the tested portable environment. Build-tool versions
are captured separately; wheel ZIP metadata and tool versions can change its
digest. Record the new wheel digest rather than requiring equality with the
historical `51ae463f...` digest. Source identity and wheel identity are separate.

## No-skip source proof

Continue in the same shell. This uses the archive, including repository-only
fixtures, and requires the historical 187-case selection to pass without skips.

```sh
(
  cd "$proof_root/source"
  "$proof_root/runtime/bin/python" -B scripts/run_tests.py \
    bilqis_mlx/semantics/tests/frame_compiler \
    bilqis_mlx/semantics/tests/partial_visible_forest \
    bilqis_mlx/semantics/tests/released_schemas \
    bilqis_mlx/semantics/tests/frame_schema \
    bilqis_mlx/semantics/tests/frame_codec \
    bilqis_mlx/semantics/tests/test_frame_codec.py \
    bilqis_mlx/semantics/frame_codec_parts/tests \
    bilqis_mlx.semantics.tests.source_atom_binding.test_binding \
    bilqis_mlx.semantics.tests.source_atom_binding.test_handoff \
    bilqis_mlx.semantics.tests.source_atom_binding.test_resolution \
    scripts/tests/bamf
) > "$proof_root/source-tests.log" 2>&1
grep -Fx 'TEST_TOTALS total=187 passed=187 failed=0 skipped=0 errors=0' \
  "$proof_root/source-tests.log"
```

## Installed-origin proof

Save the Python block below as `$proof_root/probe.py`, then continue in the same
shell. Run from outside the archive with isolated Python; no checkout or editable
installation belongs on the import path.

```sh
(
  cd "$proof_root"
  "$proof_root/runtime/bin/python" -I "$proof_root/probe.py" "$proof_root/installed"
) > "$proof_root/installed-tests.log" 2>&1
grep -Fx 'INSTALLED_TEST_TOTALS 116 0 0 0' "$proof_root/installed-tests.log"
grep -Fx 'INSTALLED_WHEEL_MODULE_ORIGINS_OK' "$proof_root/installed-tests.log"
```

Use the runtime environment created above. This is a finite
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

## #733 reproduction receipt — 2 November 2026

Executed the shell blocks above and the Python probe in fresh archive/build/runtime/
installed directories, using separately supplied existing fixtures. The source
commit was `7c8b75a418e726060945f2b9cbe296063b7d9ee4`. This did not rebuild
either source fixture or exercise the later merge candidate's complete gates.

- Python: 3.14.4. Build tools: setuptools 84.2.1, wheel 0.48.0, packaging 26.3.
- Wheel: `bilqis_mlx_private-0.5.0-py3-none-any.whl`.
- Observed wheel SHA256:
  `401169311dc7dc04898f346d3f8ba74ffbfe1aec7f0870d3c291d03ec2336c3f`.
- `TEST_TOTALS total=187 passed=187 failed=0 skipped=0 errors=0`.
- `INSTALLED_TEST_TOTALS 116 0 0 0` and
  `INSTALLED_WHEEL_MODULE_ORIGINS_OK`.
- Negative prerequisite check: with both fixture variables unset, the first shell
  block exits nonzero at the A01 access requirement before creating environments.
- Documentation and governance checks pass; `git diff --check` is clean.

This closes the recipe's verification gap only. Parent #347/#694 retains aggregate
EGM and integration obligations. No native MLX witness was rerun for this
documentation-only repair; the prior six-case receipt remains historical.

Historical receipt: `4ab0752d` passed 93/93 in the earlier installed selection.
The current 116-case result does not retroactively change that historical proof.
