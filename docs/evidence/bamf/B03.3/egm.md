# B03.3 scoped EGM and proof receipt

Issue #444; consumed unified `9104ce733e04fb9c82420428b18dfdbf5db49535`.
Issue branch: `codex/bamf02-b03-3-444-finish-20261030`.
Structural extraction: `9bb14b4`. Reviewed scope also includes the staged mirrored
test renames, exact observability assertions and B03.3 contract.

Google EGM pin: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
Fresh reviewer: native `b03_444_egm`, `fork_turns=none`, read-only, no inherited
conversation or memory retrieval. The reviewer read the actual Codex guide,
implementation-readiness/codebase-details/comprehension personas, both required
standards, contract/structure notes, original unified encoder, extracted owners
and tests. It compared the current staged scope against the original source.

Disposition: **APPROVE within #444 scope; zero Blockers, Majors or Nits.**
No prior nested test disappeared. Source validation, child lookup, shape/finite
checks, tensor names, equations, public imports and pickle identities are preserved.
The exact p4/p8 lineage/count/padding proof satisfies this child's two obligations.
The reviewer inspected code and proof receipts; it did not independently rerun
the implementer's tests. This distinction is part of the receipt.

## Executed proof

- Before extraction: 22 CPU tests passed, zero skips.
- After extraction plus pickle compatibility: 23 passed, zero skips.
- After exact lineage/count assertions: 25 passed, zero skips.
- Affected union: **66 passed, zero failures/errors/skips**. This adds frame
  embedding tests, both source-bound literal/identity witness suites and the
  source compiler to the contract's focused command. Set MLX default device to
  CPU before loading any suite. Only disposable MLX arrays are used.
- `scripts/check_module_size.py --changed-from 9104ce7`: PASS.
- `scripts/quality/check_governance_integrity.py --base-ref 9104ce7`: PASS.
- `scripts/code_smell_audit.py --changed-from 9104ce7 --check-baseline
  docs/evidence/development/code_smell_baseline.json`: zero new findings.
- `git diff --check`: PASS.
- `scripts/check_historical_abi.py`: historical fingerprints agree; zero
  prohibited executable literals. Independent external expectation remains
  advisory/unconfigured.
- `scripts/check_factory_architecture.py`: **FAIL**, unchanged B01
  `runtime/model_topology_v2.py:280 GENERIC_GRADE_IDENTITY_DISPATCH A,B`.
  #621/#622 owns that inherited category defect. This change does not modify
  that file or weaken any guard. Full integrated checks are not claimed green.

The first exact-sidecar test exposed an incorrect test assumption: atomic
sidecars have no schema scope; the compiler map retains their source task scope.
The assertion and contract now preserve both meanings explicitly. Production
semantics were unchanged.

## Acceptance boundary

IPR-0220 remains OPEN. PM-2026-10-30-002 / RC-112 / PAT-035 controls preserve the
physical teacher-policy source paths. No teacher source file changed. #444's
source handle/count proof is complete; parent B03 integration, assembled B11,
B05 provenance, B13 publication, neural learning and retention remain separate.
Only the human merges this PR or starts/resumes the durable student. No actual
student, own AdamW, teacher, champion or historical checkpoint changed.
