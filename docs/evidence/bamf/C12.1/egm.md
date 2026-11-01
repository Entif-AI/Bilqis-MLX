# C12.1 / #525 staging receipt

Consumed unified/Lane C: `bb626d75`. Feature branch:
`codex/bamf02-c12-525-manifest-20261101`.

This is a provisional portable manifest/export/compatibility boundary, not full
#525 acceptance. Direct owners A12/#364, B13/#372, C05/#378 and C09/#377 remain
open. No production source/export adapter or durable generation importer is wired.
No tensor application, optimizer reset, retained-learning, atomic publication,
learner update, graph write or operator start is claimed.

## Implementation and proof

Frozen source/export/rights records carry the semantic signature, operator/model
identities, exact address bindings, source-clearance allowlist, revocation lineage,
qualification fixtures, counterexamples, behavioral diff and resource envelope.
Canonical JSON roundtrips across two synthetic consumers. A mismatch in any of
seven binding identities rejects an adapter/weight delta, including mixed packages.
A non-delta mismatch yields only a teaching plan. Plans never authorize adoption.

Initial red: three ImportErrors because APIs were absent. Green: 18 package tests
plus 3 catalog tests. Tests also preserve the historical catalog's original frozen
prefix and append the new error rather than changing its order. Golden canonical
fixture digest: `98527cd13e7a10c65d4697277e681137f34ff55dbdf479bf842eb7f87c6372e4`.

Commands:

```sh
python3 -B -m unittest discover -s bilqis_mlx/runtime/cognitive_package/tests -t .
python3 -B scripts/run_tests.py bilqis_mlx/errors/tests/test_catalog.py
python3 -B scripts/check_module_size.py --changed-from bb626d75
python3 -B scripts/quality/check_governance_integrity.py --base-ref bb626d75
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/error_control_plane.py --check --base-ref bb626d75
git diff --check
```

All listed checks pass. Error control reports new debt 0. Every new source/test
module is below 240 lines. Root runtime and runtime/tests each retain 12 direct
Python files; the new package has its own cohesive owner and mirrored tests.

## Independent EGM

Actual cached Google EGM checkout was verified at
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Each reviewer used fresh native
`fork_turns=none` context, the actual personas/standard, issue contract and bounded
files. No inherited implementation conversation or memory was supplied.

Readiness reviewer `c525_readiness` reported five initial Majors: file inventory,
record schemas, import output/mixed behavior, canonical encoding and literal proof.
The concrete plan amendment resolved design Majors. Targeted review found one
remaining test Major: semantic malformed-input tests used noncanonical JSON,
which could conceal absent semantic validation. Tests now mutate canonical JSON
and check the exact typed error. Mixed-package and independent golden wire fixtures
also resolve the two Nits. Public export count was corrected from eight to seven.

Turn-in reviewer `c525_review` read both codebase-details and comprehension personas
and the implementation-readiness standard, all bounded source/tests, docs, issue
and central catalog diff. It found one Major: lone Unicode surrogates could escape
as uncatalogued encoding failures. Three regression tests first produced five
failures and one error. Metadata now excludes surrogate code points and cold reads
validate UTF-8 before JSON parsing. All 18 tests pass. Fresh targeted re-review:
**no remaining Major or Blocker**. Test-only filenames were subsequently aligned
with their production owners; no behavior changed.

Remaining acceptance: actual source-owned clearance and accepted A12/B13/C05/C09
receipts; tensor slice/custody/retention adoption in #526/#527; parent #381 integration.
