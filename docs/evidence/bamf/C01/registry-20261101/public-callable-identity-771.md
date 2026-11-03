# C01 public callable identity remediation #771

The complete pinned codebase-details review at `cfe7e7ed` found a Major:
facades restored class module names but left method/property functions attributed
to new private owners. Comprehension had one nonblocking historical-wheel-link
Nit. Both findings are repaired in this candidate. Earlier review receipts remain
historical; this repair does not itself claim a new aggregate EGM PASS.

## Reproduction and implementation

The literal fixture `bilqis_mlx/semantics/_public_identity/tests/public_callables.json`
enumerates all 50 declared record callables from the four original public owners
at immutable `bd62f3cb6c296151aba7b9ed5fa90ee814492494`. Before repair, those
50 cases and six common dataclass-generated methods failed their public-module
assertions: 56 failures across two tests. A separate adversary reproduced unwanted
mutation of a foreign function with a coincidentally matching qualified name.

The shared `_public_identity/module_identity.py` owner restores module metadata
on the same function/class objects. It handles class/static methods, property
accessors and wrapped generated methods. Both original defining module and the
class-qualified name must match before a class member is changed. Inherited
members are not traversed; functions from other defining modules remain unchanged.
Wrapper traversal stays within each function's original defining module, restoring
the public module identity those wrapped functions held before extraction. The four public
facades import the helper through a private alias and retain their existing
export lists. No original method body, signature, docstring, object, source guard,
validation order or compiler packing seam changes.

Six focused tests pass. They cover the 50 original declared callables, six generated
methods, literal protocol-4 public method globals and pickle readback, descriptors,
foreign/inherited functions including the name collision, wrapped functions,
signatures, docstrings and behavior. These are module-metadata and declared public
global guarantees; physical source locations necessarily belong to the new owners.

The isolated issue branch starts from synchronized Lane C, consumes the same-C
parent structure, and publishes `c27ac97d6015b34b86b14a160f8a51a685d38432`.
The parent consumes its bounded changes as `8fe94c85`, `88ad90bb` and `3174c368`.
The historical link now identifies the later 116-case recipe, without inventing a
93-case historical wheel hash.

## Complete repaired proof

Tested source: `3174c36897ac0a67c630175692cf39cf58dcf4de`.

- Fresh Git archive source selection: **193 passed, zero failures/errors/skips**.
- Fresh build environment, wheel and installed target: **122 passed, zero
  failures/errors/skips**. Every loaded Bilqis module/namespace path is installed.
- Observed wheel SHA256:
  `6b6558d5d8f44d29a988cfdc4dcdf099c8f076be535be85072140228e3142bed`.
- Native MLX frame callers: **6 passed on CPU, zero failures/errors/skips**,
  using the selection in [the preceding refresh](current-20261103.md).

The runtime reuses the dependency-pinned #733 environment. The archive, build
venv, wheel and installed target are new. The verified Atlas/conformance bundles
are supplied read-only; they are not independently regenerated or distributed.
The earlier 187/116 and intermediate 193/122 receipts retain their own source and
wheel identities and are not relabeled as proof of this source.

## Exact reproduction changes to the archive recipe

Follow [the complete environment/archive recipe](installed-wheel-probe.md), using
these exact substitutions for the repaired source:

1. Set `proof_commit=3174c36897ac0a67c630175692cf39cf58dcf4de`.
2. Append `bilqis_mlx/semantics/_public_identity/tests` to the source test command;
   replace the historical source grep command with:

```sh
grep -Fx 'TEST_TOTALS total=193 passed=193 failed=0 skipped=0 errors=0' \
  "$proof_root/source-tests.log"
```
3. In the installed probe, immediately before the case-count assertion, add:

```python
suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
    'bilqis_mlx.semantics._public_identity.tests.test_module_identity'))
```

4. Change the installed case-count assertion to
   `assert suite.countTestCases() == 122, suite.countTestCases()` and replace the
   historical installed total grep command with:

```sh
grep -Fx 'INSTALLED_TEST_TOTALS 122 0 0 0' "$proof_root/installed-tests.log"
```

Preserve the separate `INSTALLED_WHEEL_MODULE_ORIGINS_OK` grep, the one explicit
vendor-only exclusion, no-skip assertion and complete module/namespace checks.

After executing the recipe, run `python3 -B docs/evidence/bamf/C01/registry-20261101/verify_repaired_recipe.py "$proof_root"`.
This deterministic check rejects the stale 187/116 predicates, missing no-skip
totals and missing installed-origin proof. Its four focused regressions run with
`python3 -B -m unittest discover -s docs/evidence/bamf/C01/registry-20261101 -p test_verify_repaired_recipe.py`.

The extra six cases are the new owning metadata suite. The 70 repository-only
script cases and one vendor-only fixture remain covered by the full source suite.
The fixture JSON travels through the existing package-data rule and is exercised
by isolated installed imports.

## Remaining authority

Full #347 remains open with eight normalization holds, valid 171-child integrity
and empty execution order. The 14 unchanged issue-contract verifier failures are
owned by #770; no baseline, assertion or provenance requirement was relaxed.
The parent owns fresh whole-candidate EGM and human integration. IPR-0220 remains
opaque. No persistent learner/own AdamW/teacher/admission/source-release/graph
mutation or self-merge is authorized.
