# A08.1b.2 partial: A01/A07 formal source/operator join

Parent A08.1b #418; granular child issue #554.
Original isolated candidate: `codex/bamf02-a08-formal-lessons-20261029`.
Baseline: A08.1b.1 candidate `024f049`, with A08.1a governed
source-pin repair `f8b90c1`. Independent EGM: **PENDING**.

The new `bilqis.formal-source-operator/v1` and
`bilqis.formal-source-operator-set/v1` records join exactly pinned
A01 formal identities and ABI indices to A07's verified pure operator
specifications, signatures, implementation/source contracts and
operator-grant evidence digests. The public resolver loads the A01
artifact through the SHA-pinned source registry. It never infers a
law from a gloss or substitutes a different operator under an ABI
index. Unknown operators remain explicit `OPERATOR_UNREGISTERED`
debt, without shrinking the source denominator.

The source-binding resolver emits **only**
`SOURCE_PROJECTION_NOT_AUTHORITY` proposal schemas. Even its public
form does not mint a transferable attestation. A consuming Factory
boundary must call `assert_formal_source_operator_set_current`
with the independently governed A01 selection and A07 registry;
this rederives the entire join and returns no reusable credential.
All proposals remain `SOURCE_BOUND_NOT_EXECUTABLE`: source replay
is not an A13 permission or a lesson checker.

The consuming assertion compares exact canonical record bytes
after recursively checking root and nested dataclass types,
not Python `__eq__`. A caller-owned `EqAnySet` or nested
`EqAnyWitness` with overridden equality cannot pass as the
real A01/A07 join. The focused real-corpus suite remains 5/5.

The real pinned A01 corpus resolves four source-bound operators:
`BOOL_NOT`, `BOOL_AND`, `COUNT`, `SUCC`. The exact focused
`test_formal_constructive.py` suite passes **5/5**, including real
source readback, wrong-release and forged A07 contract negatives,
unknown-operator debt, and self-attested source-pin rejection.
No new static error-control or module-size findings were introduced.

**This is not completion of A08.1b.2.** The status is deliberately
`SOURCE_BOUND_NOT_EXECUTABLE`, never `ADAPTER_READY` or
`LEARNING_VERIFIED`. The remaining work is to construct source-valid
Boolean/numeric positive/contrast lessons, independently evaluate
typed gold, consume live A13 rights/epochs/visibility, prove
revocation and wrong-arity/type failures, and obtain independent
EGM acceptance. This partial source join grants no source admission,
teacher credit, model/optimizer mutation or live training.

## 2026-10-29 task-scoped formal lesson continuation

The separate `codex/bamf02-a08-formal-final-20261029` candidate
reuses the reviewed A08.1a and A08.1b.1 foundations and adds
`formal_lessons.py` with a source-replaying, task-scoped generator
and independent typed checker for the four A01-attested A07 operators:
`BOOL_NOT`, `BOOL_AND`, `COUNT` and `SUCC`.

Each public call reloads the governed A01 source pin and A07 operator
contract, then invokes A07's source-qualified pure executor against
the caller-supplied A13 task, policy, frontier, operator/operand and
numeric-domain grants. The checker separately reconstructs the
Boolean/numeric truth, rather than trusting a lesson's positive
answer or calling its generator. It rechecks live rights on every
use, so revocation, correction/rights epoch drift, wrong purpose,
release, arity and type fail closed. Numeric contrasts must exist
inside the admitted finite domain; a single-value domain cannot
invent a false alternative.

The output is explicitly
`bilqis.formal-constructive-lesson-proposal/v1` with
`TASK_SCOPED_NOT_ADMITTED`,
`SOURCE_PROJECTION_NOT_AUTHORITY` and
`LEARNING_UNVERIFIED`. No A13 grant is created or cached.
The bounded source/lesson owner suites use the real pinned A01
corpus and literal A07/A13 grant fixtures:
`test_formal_constructive.py` plus `test_formal_lessons.py`,
**13 passed, 0 failed, 0 skipped** after the canonicality
repair. Independent EGM is pending.

This is still **partial A08.1b.2**: Factory
`ConstructionProgram` registration, broader exercised variation
coverage, final A13.1/A07.2 receipt crosswalk and downstream
admission remain separate gates. Do not close #554 or A08.1b
on the strength of these task-scoped proposals alone.

## Independent review repair: canonical TypedValue validation

Goldfish worker-11 reviewed immutable `3b0004c` and found one
Major: a caller could mutate a frozen `EntitySet` into duplicate
or out-of-order values, reissue the matching A13 evidence grant,
and have a noncanonical COUNT example accepted. A mutated
`TypedValue.schema_version` also passed.

The new `_typed_exact` gate now checks the released TypedValue
schema, exact release/handle/value types and canonical sorted,
unique EntitySet invariants on every public construction and
checker invocation, before A07/A13 replay. Both adversaries
are covered by failing-before regressions. The first review is
not treated as PASS; a fresh immutable-head re-review is pending.

Targeted review of `13cf945` cleared the TypedValue Major but found
a second Major: a live-mutated lesson could falsely claim
`ADAPTER_READY`, `LEARNING_VERIFIED`, transferable source authority
or a substituted schema while still passing the checker. The
checker now reruns the exact lesson-record invariants before
source replay. Four live-field mutation regressions reject all
these relabellings. Real pinned owner suites: **13/13 passed**.
Fresh immutable-head EGM remains pending.
