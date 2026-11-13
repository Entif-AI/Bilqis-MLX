# C06 supervised salience design review

Review target: `docs/evidence/bamf/C06/neural-integration-design.md` (proposed design). Pinned EGM checkout: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Personas: Codebase Details and Implementation Readiness. Result: **FAIL** — 1 Blocker, 3 Major. This is a design review; no implementation behavior or acceptance is proven. No tests were run.

## Findings

1. **Blocker — Current-source and correction validation is not specified at the consumption boundary** (design lines 30–35, 63–65, 73–84). The plan relies on re-entering `attach_salience_labels` to verify current release and signatures, and requires revoked rights/correction to reject before neural execution. That helper calls `require_current_release`, which verifies the retained context's release and graph and compares their identifiers; it does not itself consult the accepted correction runtime or establish that the retained snapshot/registry reflects current rights. Source context registration is a distinct operation (`source_execution.py:151–159`), and merely registering the rebound compiled batch does not specify a consumption-time check. **Required fix:** identify the actual current accepted-runtime/correction and rights authority APIs, the exact dependency frontier checked, and when and how each is consulted before both forward and loss issuance; define rejection when current authority is unavailable or changed. Include a regression that changes the accepted authority after preparation and verifies the consuming path rejects before forward.

2. **Major — The digest comparison is ambiguous and does not bind labels** (lines 23–35). `BamfTrainingBatch.authority_digest` hashes release, generation, delivery and row provenance, but not row auxiliaries (`atlas_training_contracts.py:113–124`). `BamfTrainingAuthority.digest` hashes a different payload, while `training_batch_sha256` stores the batch digest (`atlas_training_authority.py:49–99`). Comparing the batch authority digest to the compiled training authority's `digest` compares different values; comparing it to `training_batch_sha256` does not independently bind auxiliary contents. **Required fix:** name the exact fields to compare, specify how re-derived signed row labels are matched to the labelled row actually consumed (including existing auxiliary conflicts), and test changed label/receipt with unchanged provenance. Do not treat the batch digest as a label digest.

3. **Major — Claimed existing primary-target guard is weaker than the required rule** (lines 63–69). `loss_bearing_bamf` currently checks only a nonempty targets tuple and at least one true mask value (`atlas_model_training.py:72–90`); it does not require a masked, executed primary typed target. `answer_loss` skips unmatched/masked decisions and can calculate only role/epistemic or zero loss (`decoder/losses.py:25–56`). Consequently preserving the existing guard does not establish the design's stated prohibition on salience-only candidate updates. **Required fix:** specify the precise qualifying decision kinds and require a matching target, true mask, and executed primary decision before issuing candidate-authorizing loss; define fail-closed behavior and tests for empty, unmatched, masked-out, and auxiliary-only targets, including no-salience compatibility implications.

4. **Major — File-level implementation and stable checkpoints are missing** (lines 16–28, 49–69). Only the new helper and test directory are named. The required changes span existing Factory dispatch, B11 forward issuance/record, backend and gradient plumbing, loss construction, and loss participation issuance; the plan does not enumerate those files as Modify, specify where supervision is carried through `_execute_prepared_candidate`, or partition implementation into independently buildable/testable phases. For example, the current Factory dispatch calls `bamf_value_and_grad` inside `_execute_prepared_candidate` (`factory_candidate_training.py:153–177`), and `_issue_loss_execution` copies dense names from the forward record (`atlas_model_contracts.py`). **Required fix:** give a Create/Modify/Delete file list and concrete signatures/data flow through these owners, including forward-record lifetime and how loss-specific head names enter the issued census; set incremental stable checkpoints with focused tests.

## Actual reads

- Worktree `AGENTS.md` (tool output was truncated; relevant BAMF design-review and verification rules were visible).
- Pinned EGM `docs/codex.md`, `agents/codebase_details.md`, `agents/implementation_readiness.md`, and `resources/document_standards/implementation-readiness-standard.md`.
- Target design in full.
- Source inspection: `bilqis_mlx/runtime/_model/salience_auxiliaries.py`, `atlas_training_authority.py`, `backbone/atlas_model_forward.py`, `backbone/atlas_model_training.py`, `backbone/atlas_model_backend.py`, `backbone/atlas_model_contracts.py`, `backbone/compiled_batch.py`, `bilqis_mlx/learning/atlas_readout/decoder/losses.py`; selected relevant portions of `runtime/_batch/factory_training_bridge.py`, `factory_candidate_training.py`, `atlas_training_contracts.py`, `runtime/_source/source_execution.py`, and `learning/_salience/atlas_salience.py`. Production files were checked for line count before reading and were under 360 lines. Some combined tool output was truncated; findings rely on the visible relevant portions and targeted rereads.

## Targeted repair dispositions

Revision 2 resolved digest and primary-target findings. Targeted review retained
one Blocker (unclosed artifact references and rights-transition identity) and one
Major (new-kind priority mapping). The one-node assumption was then redesigned.
Revision 3 uses a closed policy/fact/binding/root graph, copies exact C02
RIGHTS/POLICY/TIME dependencies, and defines owner_priority `(2, 3)`.
Fresh reviewer c06_neural_design_review returned PASS: 0 unresolved Blockers and
0 Majors for the remaining affected boundary. No tests were run. This establishes
design sufficiency, not implementation correctness or whole-parent readiness.
