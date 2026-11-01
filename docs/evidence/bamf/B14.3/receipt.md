# B14.3 | Derived cache bindings and FP32 reference policy

Issue #484; parent #375. IPR-0220 remains governing. This is staged work,
not accepted generation or source authority. Lane B sync e73e9478 consumes
unified bb626d75. Branch codex/bamf02-b14-3-484-finish-20261101 starts from Lane B,
then cherry-picks the exact same-lane #483 PR #667 implementation 783355bb
as 4ab8c5da. Final turn-in waits for #483 to integrate through unified.

Recovered original staged #484 c9c83aca binding/policy owners onto the repaired
#483 norm owner. Encoding requires explicit CacheBinding. SHA256 binds generation,
lineage, topology, source-rights epoch, causal prefix, masks, scope, key, offset and
exact integrated codec constants. Changed identities reject before decode. This
is consistency checking against a supplied expected binding; #485 and the later
production owner must obtain current source eligibility/generation authoritatively.

The artifact stores literal 45-byte header bytes, validated before decode against
its mode, binding digest and lengths. The header stores magic, mode, composite digest and true/padded
vector counts. A 256-vector full record is 2637 bytes including header and norms,
3.43359375 bits/channel. Records below256 vectors stay FP32. Padded larger records also stay FP32 when
header+payload cost exceeds3.5 bits/channel. `cache_byte_cost` includes
all record bytes. Reference evaluation accepts finite FP32 state only and gives
the evaluator a copy. Interactive inference recomputes FP32 on binding mismatch,
invalid decode, invalid typed answer or measured drift above the declared bound.

Tests mirror binding, policy, record and direction owners. Initial recovered
binding API red failed import. Recovered combined cache proof 29/29; affected
attention/cache package 43/43. An additional fixed seed484 attention fixture
measures K+V reconstruction and selects FP32 whenever L2 exceeds0.10 or chosen
answer disagrees. Measured relative L2 is approximately0.36749 with exact chosen
answer agreement; the declared0.10 bound therefore selects exact FP32 fallback.
This is observed codec error with a functioning fallback, not low-error compression
qualification. Initial fresh EGM found one Blocker (header not stored), two Majors
(padded-cost eligibility and malformed-artifact fallback), zero Nits. Incident
PM-2026-11-01-002 was filed and read back before repair. Header corruption,
257/280/289-vector over-budget records, and malformed-object probes failed red.
After repair:33 cache tests and60 affected attention/backbone/runtime-identity tests pass, zero skips. Targeted EGM re-review passes with0 Blockers/Majors/Nits. Reviewer independently
ran33/33 focused tests and manual header/mode/cost adversaries. Structure,
governance, architecture, hygiene and historical ABI checks pass. Documentation
links affected by relocation are updated in the same change.

A mandatory _model directory interruption was preserved in WorkStack and completed
as32dea836 before feature work resumed. Root direct Python files are12. Cache
owners and tests now live under _model/cache and tests/model/attention/cache;
backbone owners retain public runtime imports from _model/backbone. Seven moved
files were byte-identical;44 affected plus5 runtime-identity proofs passed.

No production attention/trainer caller, actual learner/own AdamW/teacher/checkpoint
or human-run was modified. Full B13 custody and parent cache integration remain
open. No source release, admission or learning claim is made.
