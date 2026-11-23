# #1541 adaptive candidate-budget evidence

Status: implementation evidence; activation remains closed pending fresh current-BAMF qualification.

## Authority boundary

Issue #1541 owns candidate-budget allocation only. The persistent BAMF operator now
records multi-fidelity shadow evidence at the active `2/4/8/full` rungs, but the
shadow controller has no execution, retention, publication, or proposal-selection
authority. It does not shorten the candidate horizon. Final C05 remains the sole
retention/adoption authority.

The rung sentinel uses the target rows already prebound for C05 before candidate
training. Those rows are reference target rows for bounded shadow calibration. They
are not the candidate-identity-derived fresh target draw used by final Foundation
C05, and shadow evidence must not be represented as final C05 evidence.

## Inherited calibration does not qualify

The accepted teacher state inspected before this implementation carried a bounded
128-review `factory-replay-v1` projection. That projection is inherited calibration,
not current persistent-BAMF event evidence. The current persistent operator did not
emit fresh multi-fidelity records before #1541.

Exact bounded-window result:

- reviews: 128
- early-stop recommendations: 71, all at step 8
- false kills: 4
- false-kill rate among stop recommendations: 4 / 71 = 5.6338%
- final retained candidates: 16
- retained candidates that would have been killed: 4 / 16 = 25%
- false continues: 45
- false-continue rate among continue recommendations: 45 / 57 = 78.9474%
- false continues among eventual losers: 45 / 112 = 40.1786%
- actual candidate steps represented by the projection: 1,976
- shadow-if-active candidate steps: 1,408
- projected candidate steps saved: 568
- mean projected steps saved per review: 4.4375
- projected candidate-step reduction: 28.7449%

`qualify_activation(...)` therefore returns `NOT_QUALIFIED`: the review-count and
mean-step-savings criteria pass, but the existing 1% maximum false-kill criterion
fails. The safety threshold is not weakened by #1541.

The inherited rows contain no current-BAMF wall-time economics and do not correspond
to current persistent-BAMF candidate events. The 28.7449% step-reduction figure is
therefore not a retentions/hour result and must not be reported as one.

## Fresh current-operator evidence contract

For an ordinary horizon of 12 optimizer steps, the current operator records rungs
`2/4/8/12`; other horizons use `active_rungs(...)`, with the configured terminal
budget replacing the final policy rung when necessary.

Each rung is stored inside the existing #333 candidate-evidence object and records:

- rung step and exact target-sentinel cohort identity;
- parent and candidate correct counts plus target-correct delta;
- deterministic shadow recommendation (`OBSERVE`, `WOULD_STOP`, or
  `WOULD_CONTINUE`);
- measured probe wall time and cumulative candidate-step wall time where available;
- remaining optimizer-step cost projection;
- explicit `NOT_MEASURED` retention-probability, uncertainty, future-wall, and
  preservation-sentinel fields rather than fabricated estimates;
- an explicit zero-authority marker.

At final C05 truth binding, the same evidence object records final retained/rejected
truth, false kill, false continue, projected optimizer steps saved, and projected
candidate/probe wall seconds saved when those costs were measured. Retentions/hour
remains explicitly `NOT_MEASURED` until a fresh current-BAMF window contains enough
actual candidate outcomes and wall/economic evidence to calculate it responsibly.

The per-candidate activation receipt is necessarily `NOT_QUALIFIED`. Qualification
requires a fresh bounded current-BAMF review window under the versioned activation
policy. Inherited factory-replay rows are not silently merged into that window.

No numerical false-continue activation threshold is introduced by this patch. The
live issue requires a versioned threshold justified by bounded evidence, and the
current fresh window does not yet exist. False-continue rate is therefore recorded
for calibration rather than assigned an invented safety cutoff. Likewise, the
strong-candidate early-retention path remains `NOT_QUALIFIED`: there is no accepted
fresh evidence gate yet that would justify routing a candidate to C05 before the
configured horizon. Shadow observation deliberately gathers the evidence needed to
make that later decision without granting the shadow policy new authority now.

## Verification

Focused verification after implementation and current-main reconciliation:

- `python3 -m pytest bilqis_mlx/runtime/tests/operator/observed/test_session_candidate_execution.py -q`
  - 5 passed
  - proves the 12-step shadow ladder records `2/4/8/12` without shortening the
    actual horizon.
- `python3 -m pytest bilqis_mlx/runtime/tests/operator/test_bamf_candidate_evidence_persistence.py bilqis_mlx/runtime/tests/operator/test_bamf_candidate_evidence_validation.py bilqis_mlx/runtime/tests/operator/test_bamf_candidate_multifidelity_evidence.py -q`
  - 12 passed
  - proves cold replay of rung evidence, final truth, projected wall savings, and
    fail-closed activation.
- `python3 -m pytest bilqis_mlx/runtime/tests/capability/factory/owner/test_factory_retention_owner_adversarial.py -q`
  - 11 passed
  - proves the shadow target helper remains observational and reuses the accepted
    parent score instead of rebuilding it at later rungs.
- `python3 -m pytest bilqis_mlx/learning/tests/test_teacher_vnext_replay.py -q`
  - 7 passed
  - preserves the existing versioned multi-fidelity policy behavior.
- `python3 -m pytest bilqis_mlx/runtime/tests/operator/session/test_bamf_operator_native_session.py -q`
  - 8 passed
  - preserves the native persistent-operator horizon-to-C05 orchestration after
    shadow observation was added.

The implementation also triggered the repository's mandatory structure rule because
the pre-existing candidate-evidence owner was already close to the 360-line limit.
Evidence ownership was therefore split into a 20-line public facade, a 94-line
custody/support module, a 183-line multi-fidelity module and a 274-line capture
module. Mirrored candidate-evidence tests are split into 71/140/140/79-line files,
all below the companion-test limit.

The same encounter also exposed 20 direct Python files in `runtime/bamf_operator`,
above the repository directory threshold. The evidence cluster now lives under
`evidence_parts/`, and the session coordinator helpers live under the existing
`session_parts/` package. Direct Python-file counts after the bounded reorganization
are 11 at `runtime/bamf_operator`, 13 in `session_parts`, and 6 in `evidence_parts`.

No agent neural training was run. The human production run was not stopped,
restarted, hot-patched, or otherwise mutated by this work.
