# A08.1a source-family authority EGM

Issue: A08.1a #417. Independent reviewer: fresh-context Goldfish
worker-7. Initial immutable target:
`5c18e871f5f51f770687c9e1e7910536a4430819`.
Pinned EGM protocol:
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

Initial disposition: **0 Blockers, 1 Major**. The reviewer
reproduced a same-ABI Boolean-family substitution using a real
source-qualified SKOS lexicon root. The forged
`FormalDomainBinding` retained its owner and digest, but the
inventory accepted it because it checked only ABI membership.
This changed required family obligations without source authority.

Repair: formal-bound identities now require a formal/native
ABI source tag, disjointness from SKOS concept records,
unique formal-family ownership and known family-specific
released semantic-ID namespace. A synthetic Boolean-to-SKOS,
Boolean-to-numeric and real pinned Boolean-to-SKOS negative
now fail closed. The 9,307 eligible IDs and 12,351 family
obligations remain unchanged. Prime owner suite:
15 passed, 0 failed, 0 skipped with real pinned A01 corpus.

**Disposition: independent immutable-head re-review pending.**
The initial Major is reproduced and repaired, not silently
cleared by the implementer. A08.1b remains partial; A08 parent
integration and neural/learning evidence remain open.

## Later candidate review, 2026-10-29

Independent Goldfish review of `96ae15b` reported **0 Blockers,
3 Majors**. All three exploited caller-defined equality:
source-pin tuple comparison, raw snapshot expected-ID comparison,
and lesson/answer equality. Read-only review of a separate
uncommitted repair candidate found those three mechanisms closed,
but this did not grant immutable-head clearance.

The isolated `codex/bamf02-a08-authority-final-20261029`
candidate incorporates exact-type source selection validation,
safe pin comparison, strict raw expected-ID validation and
canonical lesson/checker comparisons. Prime real-corpus A01/A08
tests: **31/31 passed**. Independent EGM of the committed
candidate remains **PENDING**, not PASS. No source/learning
admission or Lane A integration is claimed here.
