# C05.3 test compatibility repair

The user explicitly authorized this cross-lane test repair after Lane B merged
reviewed unified `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4` at
`94c81710ee5c1209d0358ee886b881d62f5f77a2`.

The incoming test expected only ValueError when replacing the init=False
fresh_learning field. On this Python3.14 host, dataclasses.replace raises
TypeError instead. Mutation was already rejected; the observed error was in
the test's exception-class expectation. The repository supports Python>=3.11.

The assertion now accepts TypeError or ValueError and also requires the error
message to identify fresh_learning and init=False. This preserves a precise
proof that the immutable non-learning marker rejects replacement. Production
translation/retention code and its authority rules are unchanged.

Red: C05.3 owner2/3 passed, one error, local validation log
`2026-10-29T14-10-13-717Z-2504.log`.
Green: the affected merged A05/B02/B03/B04/B05/B06/C04/C05 set passes
**124/124, zero skips** through the prepared Lane B environment and validation
runner. Diff check is clean. Fresh scoped EGM review returned PASS, no material
finding, and independently ran the C05.3 owner suite:3/3, zero skips.

PM-2026-10-29-002 was enriched at discovery and native readback verified;
the repair will receive a superseding native ledger receipt after push.
IPR-0220 remains open. No durable student, own AdamW, teacher, champions,
original checkpoint or source release changed. Actual source coverage,
learning and retention remain unmeasured. Human owns integration and durable
training. Lane B's unfinished private optimizer prototype is excluded from
this repair commit.
