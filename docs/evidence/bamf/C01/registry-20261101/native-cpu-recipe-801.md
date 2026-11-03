# C01 native CPU reproduction — #801

This recipe runs only the six disposable native frame callers. Portable archive,
wheel and installed-origin evidence remain separate receipts. It does not start,
resume or update a durable student or optimizer. IPR-0220 remains opaque.

Prerequisites: macOS 14 or newer on Apple Silicon, Python **3.14** with `venv`,
Git, tar, package-index access, and a clone containing the tested source below.
`python3.14` must resolve to that interpreter; its version/platform are checked
before creating the environment. No activated environment or bare `python` is
assumed. Run the complete block from the repository root.

The tested archive source is `76f55ca807e457b69447d7a04c1afe94e19ee10a`:
the exact C01 parent `2765b5df6ce0a23c9388800c13375ac2f67a98b3` consumed into
synchronized Lane C/unified `7984d787`. This identifies tested source; it does
not claim that the parent passed aggregate review. A later parent candidate
must record its own source commit and rerun the same selection.

```sh
set -eu
proof_repo=$(git rev-parse --show-toplevel)
proof_commit=76f55ca807e457b69447d7a04c1afe94e19ee10a
native_python=$(command -v python3.14)
"$native_python" - <<'PYPREFLIGHT'
import platform, sys
assert sys.version_info[:2] == (3, 14), sys.version
assert platform.system() == 'Darwin', platform.platform()
assert platform.machine() == 'arm64', platform.machine()
assert int(platform.mac_ver()[0].split('.')[0]) >= 14, platform.mac_ver()
PYPREFLIGHT
proof_root=$(mktemp -d "${TMPDIR:-/tmp}/c01-native-801.XXXXXX")
mkdir "$proof_root/source"
git -C "$proof_repo" archive "$proof_commit" > "$proof_root/source.tar"
tar -xf "$proof_root/source.tar" -C "$proof_root/source"
"$native_python" -m venv "$proof_root/native"
"$proof_root/native/bin/python" -m pip install \
  mlx==0.32.4 mlx-metal==0.32.4 numpy==2.5.4 rdflib==7.6.0 \
  cryptography==50.0.2 pyshacl==0.40.1 > "$proof_root/install.log" 2>&1
"$proof_root/native/bin/python" -m pip freeze > "$proof_root/native-freeze.txt"
"$proof_root/native/bin/python" -B - "$proof_root/source" "$proof_commit" \
  > "$proof_root/native-cpu.log" 2>&1 <<'PYCPU'
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
import platform
import runpy
import sys
import mlx.core as mx

source = Path(sys.argv[1]).resolve()
commit = sys.argv[2]
assert sys.version_info[:2] == (3, 14), sys.version
assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
mx.set_default_device(mx.cpu)
assert mx.default_device() == mx.cpu, 'NATIVE_CPU_DEVICE_REQUIRED'
os.chdir(source)
sys.path.insert(0, str(source))
targets = [
    'bilqis_mlx.learning.tests.frames.test_compiled',
    'bilqis_mlx.learning.tests.frames.test_members',
    'bilqis_mlx.learning.tests.frames.test_execution',
]
print(json.dumps({
    'source_commit': commit, 'source_directory': str(source),
    'interpreter': sys.executable, 'python': sys.version,
    'platform': platform.platform(), 'device': str(mx.default_device()),
    'command': sys.orig_argv, 'test_targets': targets,
    'packages': {name: metadata.version(name) for name in (
        'mlx', 'mlx-metal', 'numpy', 'rdflib', 'cryptography', 'pyshacl')},
}, sort_keys=True), flush=True)
runner = runpy.run_path('scripts/run_tests.py', run_name='_c01_native_recipe')
output = io.StringIO()
main = runner['main']
code = main(targets, root=source, stream=output)
print(output.getvalue(), end='', flush=True)
assert code == 0, code
assert 'TEST_TOTALS total=6 passed=6 failed=0 skipped=0 errors=0' in output.getvalue()
assert mx.default_device() == mx.cpu, 'NATIVE_CPU_DEVICE_CHANGED'
origins = []
for name, module in tuple(sys.modules.items()):
    if name == 'bilqis_mlx' or name.startswith('bilqis_mlx.'):
        paths = ([module.__file__] if getattr(module, '__file__', None) else [])
        paths += list(getattr(module, '__path__', ()))
        for path in paths:
            resolved = Path(path).resolve()
            assert resolved.is_relative_to(source), (name, str(resolved))
            origins.append((name, str(resolved)))
assert origins, 'NATIVE_SOURCE_ORIGINS_MISSING'
print(json.dumps({'native_source_origins_verified': len(origins),
                  'device_after': str(mx.default_device())}, sort_keys=True))
PYCPU
cat "$proof_root/native-cpu.log"
printf 'NATIVE_PROOF_ROOT %s\n' "$proof_root"
```

Missing dependencies fail at installation/import. Wrong interpreter, unsupported
host or wrong device fails before the test selection. A load error, skipped test,
wrong count or module loaded outside the exact archive also fails the recipe.
The package freeze, command/interpreter/device/source record and actual test log
remain together in the printed proof directory. Fixtures in this six-case
selection are disposable; this is not an A01 source-admission or learning proof.

## Observed receipt

The literal block above ran successfully in a fresh venv from a fresh Git archive
on 3 November 2026. Observed Python 3.14.3, macOS 27.0.1 arm64, MLX/MLX-Metal 0.32.4,
NumPy 2.5.4, rdflib 7.6.0, cryptography 50.0.2 and pyshacl 0.40.1. All six tests
passed in 0.590 seconds, with zero failures/errors/skips. Device before and after
was `Device(cpu, 0)`; all 321 loaded Bilqis file/namespace origins resolved inside
the exact archive. The package freeze and log are retained with that archive.

Two controls exercised the same extracted Python block before any test ran:
changing only the device selection to GPU fails with
`NATIVE_CPU_DEVICE_REQUIRED`; executing it in a new Python3.14 venv without
installed dependencies fails with `No module named 'mlx'`. Both return nonzero,
with no TEST_TOTALS receipt and no student/optimizer operation. These controls
change temporary copies only; the documented recipe always selects CPU.

Archive SHA256: `3302aa04acd96301e864bbc5f89202a9da045d714c06bebd65726b6bbf2aa93a`.
Package-freeze SHA256: `3e4cbd8577e029ca972a33c43e88fc205355ab8581517e46d34a147b29511d7e`.
Native-log SHA256: `e1c409b3fc9a5622acc05abb1a168a3dec1a069f356e9c7224e108030aad5a28`.

This repairs the bounded #801 reproduction defect for parent consumption. It does
not clear #800 or claim aggregate C01 readiness. The parent must consume the
recipe and rerun it against its next final source head before the existing final
aggregate review; the C01 review episode/cap remains unchanged.

## Parent aggregate replay — 3 November 2026

After #800 and #801 were both consumed into the active #347 continuation, the same
literal recipe was rerun from fresh archive source commit
`1205b9904bab144679972dba1d652dfa51fed4f6` in a fresh disposable native venv.
Observed Python 3.14.4 on arm64 macOS, MLX/MLX-Metal 0.32.4, NumPy 2.5.4,
rdflib 7.6.0, cryptography 50.0.2 and pyshacl 0.40.1. CPU was selected before
the test selection and remained selected afterward. All six native frame callers
passed with zero failures, errors or skips, and 322 loaded Bilqis file/namespace
origins resolved inside the exact archive.

Parent replay receipts:

- source archive SHA-256:
  `1ed3131252bad408e118e5eb84eb07f5c2866043e669a7d63cb0da1bbba54169`;
- package-freeze SHA-256:
  `3e4cbd8577e029ca972a33c43e88fc205355ab8581517e46d34a147b29511d7e`;
- native log SHA-256:
  `d85f3e60e46e22f25b2774cf6df77058ec9c1df685b255adb816ac18e80944b7`.

This parent replay remains a disposable native witness only. It performs no student,
optimizer, teacher, checkpoint, graph or source-admission mutation.
