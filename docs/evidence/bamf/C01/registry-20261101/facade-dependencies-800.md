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
