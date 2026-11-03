# C01 facade dependency ownership — #800

The original facade modules owned their Python-function globals. Extracted
functions keep their identity, but their physical module globals are different.
Restoring `__module__` alone cannot preserve public dependency/fault hooks.
This is structural hook preservation; no normal source-validation bypass is
asserted.

The independent ordinary design review selected one rule: every original
facade-global Python-function dependency is resolved through that facade module
at the point of use. Class objects remain unchanged. New phase helpers absent
from the original facade remain private. Algorithm order, arguments, source
proofs and typed guards are preserved. There is no runtime code rewriting,
replacement implementation, proxy callable or new source authority.

A read-only module reference handles cyclic imports safely; each use reads its
current attribute. Source edits qualify those references in all four extracted
owners, including underscore helpers and externally imported facade functions.
They remove obsolete function imports and per-call captured imports. Existing
explicit module-attribute calls already obey the rule and remain valid.

## Reproducible census

`bilqis_mlx/semantics/_public_identity/facade_contract.json` records the four
pre-extraction Git sources, source SHA256s and facade Python-function names.
The original revisions are the parents of splits `46c2edae`, `f683f9f9`,
`e6a94f11` and `ff2fc3d6`, respectively. They are evidence, not a second semantic
catalog or configurable runtime policy.

Run the census without writing any model/source state:

```sh
python3 -B -m bilqis_mlx.semantics._public_identity.facade_dependencies
```

It imports the four owners and inspects their physical functions, methods,
nested functions and comprehensions. It checks original facade **names**,
regardless of the current value or function identity. AST checks separately find
captured imports (including aliases), assigned aliases, defaults and closure
captures. Class metadata and code remain untouched.

The before report `facade-capture-before-800.json` was generated in a fresh
process against a Git archive of unmodified source
`70d3b398f5c05380b16de878432d6bc25617a25e`, using the same census implementation.
It reports 54/25/55/38 global dependency routes for compiler/forest/schema/released,
plus separate AST capture observations which overlap those routes. These counts
use the recursive census definition; the issue's older 168-route summary is not
substituted for this report. The repaired source reports zero in every owner.

## Red/green and literal consumers

The initial whole-owner test failed in all four families. A separate captured
module-import-alias control also failed before extending the census to cover it.
The seven new tests now pass with the pinned A01 artifact supplied, zero skips.
They reject captured globals/nested calls/import aliases/defaults/closures and
accept direct facade lookup. Actual public consumers verify:

- compiler context approval receives the original visible envelope/task/frontier;
- partial-forest validation reconstructs then recompiles through its facade;
- frame construction re-enters occurrence identity while preserving exact class,
  fields and canonical bytes;
- real pinned released-schema lookup enters the Atlas loader then released-body
  loader with unchanged source verification and result.

The complete source selection passes **208/208**, zero skips, with both existing
A01 and conformance fixtures supplied read-only. Those include source-positive,
forged-source, callable/class identity and original owner tests. No fixture is
regenerated or admitted by this work. Archive, installed-origin and native
receipts follow on the exact source commit; no aggregate EGM is claimed here.

This is scoped #800 engineering for canonical #347 consumption. The parent keeps
its existing review episode/cap and final aggregate decision. The separate #801
recipe must be rerun against the parent's final source. IPR-0220 remains opaque.
No actual student, own AdamW, teacher, source release, graph, admission, human-run
or self-merge mutation occurs.

Ordinary independent GPT-6.1 Terra High implementation review found one
`MECHANICAL_PROOF` gap in the census, not a remaining production capture:
fixed-name `getattr` aliases/defaults were not detected. Three new controls
(`getattr` alias/default and lambda default) failed before repair. The repaired
census handles them and passes all three census tests, zero skips. The reviewer
read the bounded two-file correction and cleared that specific finding without
another whole-candidate review. This is not arbitrary Python metaprogramming
coverage; the production ownership rule is explicit facade attribute lookup.

## Final exact-source packaging and native proof

Tested source: `02115a8060319bf8843abe9127307358fc10f8be`.
The preceding checkout selection passed 208/208; a fresh archive of this final
source passed **208/208**, with zero failures/errors/skips. A fresh build venv,
wheel and isolated installed target passed **131/131**, with zero
failures/errors/skips and every Bilqis file/namespace origin under that target.
The one existing vendor-only source fixture remains explicitly excluded from the
installed selection and is included in the 208-case archive selection.

Observed wheel SHA256:
`ef55008ffbe091d294450140470cb7be1f0c02b467457c386fdca11a791f04a9`.

The complete #801 native block was executed again in a fresh pinned native venv
and fresh Git archive, changing only `proof_commit` to this exact source.
It passed **6/6** on CPU, zero skips, in 0.552 seconds. Command, Python 3.14.3,
MLX/MLX-Metal 0.32.4, other package pins, before/after device and 321 archive-origin
receipts are retained together. No persistent learner/optimizer is opened.

For archive/wheel reproduction, follow the complete
[installed recipe](installed-wheel-probe.md), substituting this source commit.
Append `bilqis_mlx/semantics/_public_identity/tests` and
`bilqis_mlx/semantics/tests/public_identity` to its source selection. Add
`public_identity` to the installed probe's semantic test-package tuple and add
the existing six callable-identity cases as specified by
[the identity recipe](public-callable-identity-771.md). Keep the single vendor
exclusion, no-skip assertion and every module/namespace origin check. The correct
source and installed success predicates for this source are:

```sh
grep -Fx 'TEST_TOTALS total=208 passed=208 failed=0 skipped=0 errors=0' \
  "$proof_root/source-tests.log"
grep -Fx 'INSTALLED_TEST_TOTALS 131 0 0 0' "$proof_root/installed-tests.log"
grep -Fx 'INSTALLED_WHEEL_MODULE_ORIGINS_OK' "$proof_root/installed-tests.log"
```

Validate these exact declared totals with the existing mechanical recipe owner:

```console
python3 -B docs/evidence/bamf/C01/registry-20261101/verify_repaired_recipe.py "$proof_root" \
  --document docs/evidence/bamf/C01/registry-20261101/facade-dependencies-800.md \
  --source-total 208 --installed-total 131
```

The contract verifier passes its 214 indexed owner/child identity/fingerprint
checks. Registry integrity remains valid with 171 children; the same eight
normalization holds and empty executable order remain. The workstack command
therefore intentionally exits 1 and is not represented as an executable plan.
Structure/governance/architecture/semantic boundaries/docs/whitespace pass;
base-aware error control has zero new debt, and changed-code hygiene has zero
findings. Historical ABI enforcement remains advisory locally without an
independent expected fingerprint. Source bundles are supplied read-only, not
regenerated or distributed.
