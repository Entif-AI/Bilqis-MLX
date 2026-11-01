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
