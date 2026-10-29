# A08.1b.1 source identity and attested-relation checker candidate

Parent A08.1b #418; granular GitHub child issue #553.
Original isolated candidate: `codex/bamf02-a08-identity-20261029`.
Baseline: A08.1a governed-source-pin repair candidate `f8b90c1`,
superseding the rejected wrapper candidate `ae2faa1`, based on
Lane A `915e22a` and reviewed unified `6b54600`.
Independent EGM: **PENDING**. No child or parent closure is claimed.

The source-lesson checker now independently reconstructs the
source-qualified obligation, exact source identity, attested relation
triple, source-valid contrast, answer modality, checker contract,
constituents, prerequisite closure and exercised variation axes.
It does not call the lesson generator or trust a generator-provided
gold answer. A forged source reference, unattested contrast, invented
variation axis, wrong prerequisite or foreign release fails closed.
The relation generator requires a distinct attested contrast from a
**different source identity**. Two true relations for the same queried
source are not mislabeled as a negative without a target/predicate cue;
when no unambiguous contrast exists, the obligation remains uncovered.
Both positive and contrast endpoints enter the constituent and
prerequisite closure. The lesson evidence digest binds the exact
positive and contrast facts to their A01 obligation. Each declared
variation axis is witnessed by distinct source facts, not a free-text
claim.

Prime focused verification with the pinned real corpus:
`test_atlas_projection.py` and `test_skos_curriculum.py`,
**32 passed, 0 failed, 0 skipped**. The checker-independence
regression replaces the generator with a failing stub and still
checks exact identity and relation answers. Synthetic source-attested
fixtures cover relation positives, same-source true-relation rejection,
cross-source contrasts, exact prerequisite closure and forged negatives
even when their fact digest is recomputed.

The current real pinned A01 corpus has **no admitted SKOS semantic
relation triples**. It therefore emits no real
`source_attested_relation` lesson. This is an explicit source fact,
not a reason to invent relations or claim a missing implementation
as learned. Real positive-identity lessons are source-attested and
remain `LEARNING_UNVERIFIED`.

The checker proves a source fact, **not** current training or serving
permission. A13 source rights (purpose, tenant, epoch, correction
generation, time and scope) are separate mutable authority and must
be consumed by the A08.1b.5 execution/admission gate. A08.1b.1 does
not mint a local grant or convert source evidence into rights.

This candidate changes no source-release admission, A01 v1 artifact,
ABI allocation, model/optimizer state, teacher credit, or lane
integration. The source-authority candidate must receive EGM PASS
and enter Lane A before this dependent child can be turned in.

## 2026-10-29 source-authority-aligned continuation

The isolated `codex/bamf02-a08-identity-final-20261029` candidate
rebases this source-independent checker behavior onto the exact-type
A08.1a source-pin repair at `1f30656`. The cherry-pick conflict was
aborted without modifying the original candidate, and the source
checker, evidence-bound contrast rules and discriminating tests were
reapplied directly. The checker never calls the lesson generator;
all public consumers still reload the pinned A01 artifact and return
non-authoritative source projections only.

Focused synthetic tests confirm independently checked source identity
and relation facts, cross-source contrast, exact prerequisites,
same-source true-relation ambiguity, forged evidence/variation
rejection and non-string answer rejection. Real pinned A01/A08 owner
suites: **35 passed, 0 failed, 0 skipped**. A fresh immutable-head
Goldfish review remains required before final turn-in. This is not
A13 source-rights issuance or learner retention evidence.

## Final A08.1b.1 independent disposition, 2026-10-29

Goldfish worker-11 independently reviewed immutable
`9afa1f9ed4c94480837ba1ac0fd243287606cf3e` and returned
**EGM PASS, zero Blockers/Majors**. From a temporary archive of that
exact commit, it ran the real pinned A01/A08 owner suites:
**35 passed, 0 failed, 0 skipped**. It verified independent source
replay, source-attested contrasts, full constituent closure, forged
evidence rejection, no transferable source authority and no A13
rights issuance. The implementation is now on Lane A; the A08.1b
parent remains open for sibling constructors and Factory integration.
