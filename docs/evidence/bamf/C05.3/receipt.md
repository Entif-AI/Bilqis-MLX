# C05.3 | Immutable evidence and uniform Factory authority preflight

Issue #503; parent #378; status IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION.
Authority IPR-0220. Lane C codex/bamf02-c-runtime; draft PR #550.
Consumed unified 6b5460032fc0b19115843cce95fe8be9582af141,
already contained at baseline cd84caed7580d9b6dcc5d02d1a9bff7f82497f7b.

## Historical result and mandatory translation

FrozenHistory stores exact canonical UTF-8 JSON bytes and their independent byte
SHA. Its v1 payload preserves original native-assessment digest, generation,
cohort, rubric, policy epoch, scope, source/family/capability census, integer scores,
solver contracts and provenance-safe replay records. It does not serialize raw
CapabilityResult.score=1.0 through contract_digest. Cold construction checks exact
schemas, native DAGReceipt validity, generation/source/release identities, measured
versus reserved costs, replay/contract/scored-case count alignment and canonical
bytes. record() returns a fresh decoded copy rather than rewriting the original.

TranslatorSpec/v1 pins implementation ID/version/digest, source and destination
rubric/policy/scope/families, exact destination capability census and explicit
uncertainty. A callback receives the immutable historical record and returns exact
integer score tuples. Duplicates, missing/foreign capabilities, invalid counts,
foreign source contracts and expected decoder errors fail closed. Translation/v1
binds original byte SHA and full translator contract; fresh_learning=False is
non-settable. A changed-rubric retrospective score0/3 to3/3 leaves original0/3 bytes
unchanged. AssessmentPair and retain_candidate reject translated receipts directly.
No normalized historical difference counts as fresh learning.

## Uniform source and admission boundary

ReleasedEvidence recomputes the actual native AssessmentScopeContract from a
verified ExecutableFactoryRelease and exact assessed capability census. C05 scope
identity is contract_digest(native scope); approved policy, independently frozen
family census and full case census are explicit bridge inputs. Target and separate
prerequisite assessments must name the same current complete generation. Declared
native release edges alone select prerequisite proofs; approved rational thresholds
are bound into the request. Missing or incorrect proof holds the affected target;
an unrelated unfinished grade neither grants nor denies it.

The actual ExecutableAdmissionReceipt.verify_baseline now owns the pre-existing
baseline condition, reused by runtime/admission and this adapter: admission step
cannot exceed current step; equal step requires matching student SHA; graph identity
must agree. No alternative custody engine is introduced.

C05 authority requests bind release, target, complete generation, native checkpoint/
step, graph, source bindings, policy, evidence and thresholds. Source/rights,
approved promotion policy and required admission lease produce distinct typed,
request-bound authority receipts. Missing, held, malformed, failing or foreign
receipts yield HELD/LEASE_REQUIRED. A promotion dictionary cannot replace actual
native admission or another authority. All grade labels and exact/neural routes
face the same evidence conditions. Existing native promotion retry still keys the
retained checkpoint plus introduced scope; cohort changes alone cannot rearm it.

These are pure preflight adapters exported through candidate_evidence/exam_execution.
They never call _commit_prepared_successor or publish/admit a release. Actual C07
lease consumption before that native writer remains a required integration seam;
no fake AtlasAdmissionLease implementation or Prometheus adopter bypass was added.

## Verification and independent EGM

Red: absent new modules; then seven expected failing rehashed-malformation
assertions reproduced the cold-reader defect. Raw expected-red-malformations.txt
is retained. The existing runner counts failed subtests as failed tests and reports
an inconsistent negative passed subtotal on that red run; no acceptance uses that
subtotal. Final114 affected history/authority/solver/retention/native admission/
Factory/title/witness tests passed, zero failures/skips (tests.txt). Existing owner
API exports import correctly. git diff --check passed. No MLX proof is claimed.

Fresh Goldfish c05_3_goldfish read pinned EGM
b3a35956759bf7f024af2ff061b2e0b44b438e4c and live #503/#378/#380. Cold review
closed scope/encoding/translator/authority interface gaps before code. Implementation
review found one major: rehashed malformed replay records passed cold construction.
PM-2026-10-29-002 was enriched and native-Sheet read back before repair. Adversarial
schema/count/generation/cost/extra-payload/canonical-byte tests now reject it.
Targeted re-audit PASS, no remaining blocker/major in this fixture-level slice.
Reviewer inspected114 passing tests; it did not independently execute them.

## Remaining qualification and continuation

Actual A08/A09 source-family/Factory bridge, C07 persisted lease/adoption enforcement,
B12/B13 generation/checkpoint bytes and native backend integration remain pending.
Frozen fixtures and authority callbacks do not prove real source-rights admission,
retained neural gain, rollback or cold resume. C05 parent acceptance stays open.
No actual student, AdamW, graph, optimizer or private-source operation occurred.
Issue #503 stays open; PR #550 stays draft/unmerged. Next dependency-ready leaf:
C06.1 #504, using accepted A06/B01 contracts and frozen A09/B11 boundaries.
