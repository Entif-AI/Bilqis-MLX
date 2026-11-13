# C07.1b scoped pre-adoption revalidation candidate

Issue #510, parent #508/#380. Status: PRE_ADOPTION_CHECK_PROVEN;
ACTUAL_ADOPTION_BLOCKED; SCOPED_EGM_PASS.

Reviewed unified consumed: 7ad8f8a. Lane C source: ead92a6.
Isolated candidate: codex/bamf02-c07-1b-20261029.

The existing native prepared-successor gate already revalidates
checkpoint digest/optimizer step, frontier, evidence ledger, plan and
the exact staged successor. This patch additionally requires the
current source and answer implementation registries when an explicit
Atlas lease is present and checks both descriptor sets against the
staged executable successor immediately before any adoption executor.
Changed source or answer code fails closed with distinct BAMF reasons.
Missing registries cannot silently authorize an adopted successor.

Without a lease, the exact proposal remains STAGED with an explicit
operator action and no new registry requirement. One already issued
lease still applies across three independently revalidated proposals;
no new human prompt is introduced per candidate.

Focused owner tests: 17 passed, 0 failed, 0 skipped. No actual neural
updates, retained generation, source promotion or admission occurred.
The production B13 accepted-run owner, A09/A12 source authority and
atomic prepared-successor commit are still required before #510 can
close. This candidate does not pretend disposable fixtures are real
run custody.

## Independent review

Fresh Goldfish worker-21 reviewed immutable code
`8fba7685dfd4c4265b11e6c0f7cd3962a3b08844` and returned
**scoped EGM PASS, zero Blockers/Majors**. It verified the native
frontier/checkpoint/proposal recheck, unleased STAGED behavior, leased
source/answer descriptor revalidation, missing-registry and drift
negative tests, and the preserved adoption exclusions. The reviewer
independently reran the same three focused owner suites: 17/17 passed,
zero skips. It made no code or external changes.
