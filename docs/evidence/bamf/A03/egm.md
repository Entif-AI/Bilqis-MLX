# A03 independent EGM review and repair

Immutable review target: `7439f0a4483559f15da21e817fc7743a914126b8`.
Reviewer: fresh-context Goldfish worker-3, read-only.
Prime tests: `test_frame_adapters.py`, 11 passed, 0 failed, 0 skipped.

The independent reviewer found **zero code Blockers and zero code Majors**
in A03.3. It checked exact canonical append-only membership, every-node
graph digest, native-vs-graph authority, recursive signature/token-index
identity, and positive/negative tests. COUNT, SUCCESSOR and DIV correctly
retain their distinct native contracts; historical ADD/SUB/MUL/EQ/LT/LE
remain graph-owned.

One Major was documentation-only: the original A03.3 receipt still
described a superseded root-versus-child rule, contradicting the code
and its later addendum. The paragraph was corrected to the exact
append-only membership rule without changing code behavior.

Disposition: **PASS** after the targeted independent readback of
`222fc9b`. The reviewer verified that the corrected receipt matches
the implementation and that this report faithfully distinguishes its
own read-only inspection from the prime's 11/11 executed tests.
No Blocker or Major remains in the reviewed A03.3 scope. No neural
training, source admission or merge is authorized by this report.

## Separate A03.1/A03.2 independent review

Goldfish worker-2 reviewed A03.1/#402 and A03.2/#403 at immutable
`c69b3e2`. It found zero Blockers and two Majors:

1. Canonical frame-instance deserialization accepted a permutation
   of bindings with the same content digest, because schema-role
   order was not bound into the wire record.
2. Formal ABI concepts absent from `snapshot.concepts` could pass
   type checks using caller-invented role-allowed types.

Both were reproduced with failing-before tests and repaired in the
current lane candidate. Frame instance v2 binds explicit schema-role
order and rejects permutations. Formal-domain binding now consumes
the existing source graph and adapter identity, verifies node digest
and declared type, and fails closed without that authority.
Prime tests after repair: frame-schema 14 passed/1 optional skip,
actual-source adapters 11 passed, codec 14 passed, context 14 passed.

The worker-2 findings are not silently marked cleared: a fresh
independent immutable-head re-review is required before A03.1/A03.2
receive final EGM PASS. A03.3's separate PASS above remains valid.
