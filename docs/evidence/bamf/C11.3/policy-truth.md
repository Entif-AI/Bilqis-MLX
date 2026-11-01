# C11.3 / #524 operator policy truth repair

Consumed unified/Lane C: `bb626d75`. Issue-specific branch:
`codex/bamf02-c11-524-provenance-20261101`.

The existing resource/rubric panel advertised independent fresh generalization for
Factory releases. That contradicted the controlling 27 October assessment policy.
It now displays fresh routine, fixed promotion and inactive generalization.
Historical rubric descriptions remain intact, explicitly labeled as lineage only.
No training, scoring, admission, scheduling or saved-state behavior changes.

Red: both new user-visible regression tests failed against the untouched base.
Green: policy + BAMF metrics + read-only watcher selection passes 10/10, including
its real detached snapshot command and unchanged-journal proof.

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/presentation/tests/test_operator_policy.py \
  bilqis_mlx/presentation/tests/test_bamf_metrics.py \
  bilqis_mlx/presentation/tests/test_bamf_watch.py
python3 -B scripts/check_module_size.py --changed-from bb626d75
python3 -B scripts/quality/check_governance_integrity.py --base-ref bb626d75
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/error_control_plane.py --check --base-ref bb626d75
git diff --check
```

Tests use isolated `/tmp/c524-venv` with the repository semantic requirements and
cryptography; default host Python lacks those dependencies. Deterministic gates
pass with new error debt 0. `bilqis_mlx.cli train --help` succeeds in that same
isolated environment. No durable student command was issued.

Fresh EGM reviewer `c524_review`, using native `fork_turns=none`, read the actual
pinned codebase-details and comprehension personas, implementation-readiness
standard, issue contract, current authority, implementation, tests and runbook.
Disposition: no Blocker, Major or Nit for this bounded repair. It did not claim to
independently execute the supplied tests.

This is not full #524 acceptance. Complete candidate/source/delivery/debt/promotion/
fresh-retention/learned-transfer provenance and real launch/resume/resource custody
still require accepted production observations and #522/B13/A12 interfaces. Keep
#524 and C11 #384 open. Current generalization remains inactive.

## Continued provenance implementation

The same issue branch now implements #524's separate optional evidence readout in
`atlas_evidence.py`, consumed by the existing `atlas_metrics.py` receipt boundary.
Candidate/parent/delivery digests, actual delivered row count, grade/capability
debt, promotion attempts, fresh whole-school retention and learned transfer remain
separate. Score source/rubric identities survive independently. Missing, measured
empty and zero remain distinct; one observed debt collection never implies the
other was observed. Historical policies remain lineage only. The original
eligible-vs-held census, GREW and retained-step owners are unchanged.

The initial new test failed with a missing API. Seven new evidence tests now cover
literal expanded readout, deep immutable copy, grade relabeling, malformed-record
view preservation, missing/empty/zero distinctions, safe Unicode labels and invalid
controls. The existing ASCII terminal renderer remains unchanged; the evidence
panel uses JSON Unicode escapes to preserve otherwise ambiguous labels.

Fresh readiness review `c524_review` identified two Majors: ambiguous Unicode
bounds and missing/partial-debt rendering semantics. The concrete plan clarification
resolved both; targeted readiness review was clear before implementation.

Fresh turn-in review `c524_evidence_review` used native `fork_turns=none` and the
actual pinned codebase-details/comprehension personas and implementation-readiness
standard. It read the contract, plan, runbook, implementation, tests and bounded
renderer/watch integration. It found one Major: ordinary terminal dimensions
clipped evidence and could hide final rows. A real 80x24 subprocess with 40 debt
rows and 20 historical policies failed six literal assertions before repair.
`--once --atlas-details` now writes the complete observation report outside the
fixed viewport, preserving every row and digest. The followed panel points to the
complete snapshot command. Targeted independent re-review: no remaining Major or
Blocker. No new CLI flag, persistence or renderer policy was introduced.

Focused evidence/policy/metrics/watch proof: **18/18 PASS**. Existing detached
watcher regression selection: **9/9 PASS**. Both real snapshot subprocesses preserve
journal bytes, mtime and directory contents. Structure, governance, architecture,
docs, error-control delta (new debt 0), and diff checks pass. All changed/new source
and companion test modules are below 240 lines.

Full #524 is still open: these are structurally validated supplied observations,
not accepted production producer/source/evaluator authority. Actual production
observation issuance, parser-tested operator launch/resource custody and the
#522/B13/A12/C05 acceptance receipts remain required. No fresh generalization,
student/optimizer write, retention waiver, self-merge or operator start occurred.
