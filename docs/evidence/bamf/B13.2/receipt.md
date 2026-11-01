# B13.2 | Complete unbound numerical cold-read witness

Issue #479, parent #372; governing IPR-0220. The feature branch is
codex/bamf02-b13-2-479-cold-resume-20261101, cut from synchronized Lane B/unified
70e37ae27214061dcc1712503eae6741a2e3781e. It consumes the exact same-lane staged
#478 dependency PR #672 at6ced8eff290f3e0ba44674acd4c780427e8ddf94. That dependency
is unaccepted; its run-directory boundary finding PM-2026-11-01-004 remains open.
This witness uses direct save/load on a fresh, regular temporary directory,
not that publication/lock path. The dependency branch is unchanged.

## Executed scope

The existing B01/B12 initializer creates every actual declared tensor without
patching the ledger or shape validator. The fixture deliberately remains UNBOUND.
It has214 parameter tensors /79,469,798 scalars and856 serialized weight, first
moment, second moment and scalar/per-row count arrays. Nonzero first/second moments
and a local count ensure the readback cannot pass by resetting everything to zero.

The test compares the original candidate against same-process cold loading and
a separate clean Python process. SHA256 witnesses cover every named array byte,
dtype and shape; teacher cursor/next seed, policy/row ages/clocks, motif state,
semantic ABI, compiler and correction metadata must match. It also executes all
three existing B11 numerical backbone groups and requires identical finite output
on CPU. This is not the complete source-admitted B11 model dispatch. Every bundle
file digest remains unchanged after both reads.

The existing100GiB disk reserve is exercised without a patched headroom check.
Temporary numerical state and files are discarded after proof; no binaries enter
Git. No actual student, teacher, native optimizer, checkpoint or human-run changes.

## Reproduction

```sh
BILQIS_BAMF_FULL_WITNESS=1 python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_full_resume.py
```

Initial red: missing full_resume_probe import. Complete opt-in proof passed before
adding an explicit finite-output assertion. The complete bundle suite then passed21/21, zero skips, with the full witness
enabled. The fixture preserves nonzero row/scalar counts, row ages and an explicit
optimizer step. The final fixture with consistent row-count/age samples and optimizer step12
passes the opt-in full test. Structure, governance, architecture, documentation,
changed-path hygiene and exact base-aware error-control checks pass with zero new
debt. No guard or baseline changed.

## Remaining acceptance

This is a numerical custody slice, not #479 completion. Actual Factory next-visit
selection, source-qualified retained learning and next optimizer-step equivalence,
genuine frozen historical-v1 readback, destination CUDA/Metal parity and complete
production-model dispatch remain NOT_MEASURED. CPU-to-CPU clean-process parity
cannot qualify cross-backend continuation. Independent EGM is pending. An earlier review of the separate superseded #478
recovery failed with workspace-credit exhaustion; a new review is requested for
this bounded #479 proof.

## Review repair and exact commands

At initial code head add320423a68014cd9a623f2ae80a876b00335bf, EGM and author
review found late baselines and omitted HP/full teacher/provenance observations.
PM-2026-11-01-005 was filed and read back before repair. Mutation controls failed
red for a saver changing nested expected state and a first reader changing or
adding files. The repaired harness deep-detaches its original-state observation
before save and snapshots files before either explicit read. It records optimizer
hyperparameters, full teacher/provenance, evaluation identity and outbox payloads;
the upstream owner separately authenticates derived outbox event IDs.

The final full-suite command is:

```sh
BILQIS_BAMF_FULL_WITNESS=1 python3 -B -c 'import mlx.core as mx; mx.set_default_device(mx.cpu); import runpy,sys; sys.argv=["scripts/run_tests.py","bilqis_mlx/runtime/tests/custody/bamf_bundle"]; runpy.run_path("scripts/run_tests.py",run_name="__main__")'
```

The bounded negative controls run with:

```sh
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_full_resume_controls.py
```

Exact local gate commands use consumed unified70e37ae2:

```sh
python3 -B scripts/check_module_size.py --changed-from 70e37ae27214061dcc1712503eae6741a2e3781e
python3 -B scripts/quality/check_governance_integrity.py --base-ref 70e37ae27214061dcc1712503eae6741a2e3781e
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/error_control_plane.py --check --base-ref 70e37ae27214061dcc1712503eae6741a2e3781e
python3 -B scripts/code_smell_audit.py --changed-from 70e37ae27214061dcc1712503eae6741a2e3781e --check-baseline docs/evidence/development/code_smell_baseline.json
python3 -B scripts/check_historical_abi.py
```

Before this review repair,21 full bundle tests and all named local gates passed.
The repaired controls pass2/2. The final full-suite totals and independent
re-review disposition are recorded below once obtained.
