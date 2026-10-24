# CURRENT SUPERSESSION | 2026-10-23 | Prometheus direct-U7C + C promotion sweep

This supersedes the issue-349 run snapshot below for current operator state. The active
run is `runs/codex-0001-prometheus`, generation **27343**, factory release
`83f9f052e40983b879a9e0495ad93d3d3fce31d10e0d12395e0b12499b17c654`.
The causal student is SHA `83322a22071e2ecaee149b6f0990e9ef73f21afe66ceff65466f0ddafe865c63`
at native AdamW step **142748**, Grade B `MAIN`, queue
`B.AND → B.OR → B.XOR → B.IMPLIES → B.IFF → B.COMPOSITE → B.IDBOOLOPS`,
visit **19463**. A bounded repair reproduction consumed the already-due `B.NOT` visit
but retained no candidate update; student SHA and AdamW step remained unchanged.
Canonical open-ended optimization remains human-only.

Grade B now admits `NOT, AND, OR, XOR, IMPLIES, IFF`, plus `COMPOSITE` and
`IDBOOLOPS`, all through direct typed Boolean-AST/U7C source construction with no
world records. B remains nongating debt. Historical ADR-090's at-most-20% candidate-
visit policy is superseded by **ADR-094's bounded grade-turn cadence**: after at most four completed non-B
training turns, B receives one complete pass over every currently imperfect admitted
B capability, then yields for four further non-B turns. At generation 27189, the
next reconstructed B pass is already due and contains all eight admitted B capabilities;
the latest cumulative B slice is 49/96 (51.0%). The active C promotion sweep remains
uninterrupted and B takes the next ordinary training turn after it resolves. Commit
`2ed45db` also separates capability-scoped row identity
from record-scoped source identity, repairing the teacher-miss collision that caused
`TEACHER_MISS_HISTORY_IDENTITY_CONFLICT`. Generation 27116 removed obsolete
world-based B miss debt and rekeyed direct-U7C misses; immutable historical evidence
was not rewritten. Fragile OR/XOR replay now understands direct-U7C records and
reserves mandatory preservation capacity before optional fresh support, preventing
`FRAGILE_PRESERVATION_BATCH_CAPACITY_EXHAUSTED` without weakening source truth.
The later `TEACHER_WEAKNESS_TARGET_IDENTITY_CONFLICT` was a distinct source-generator
defect: `B.COMPOSITE` deduplicated identities only inside each 12-row generation
cycle, while trainer draws request 32 rows and concatenate multiple cycles. A later
cycle could therefore repeat the same capability-scoped semantic row with different
`composition_pass` metadata. The public draw now deduplicates across the complete
requested batch, and the generic factory boundary independently rejects any adapter
that returns duplicate row IDs.

ADR-093 clarifies the automatic C mean-stability sweep. A fresh complete grade mean
strictly above 90% freezes the initial current-grade score vector. The canonical
one-pass sweep then replaces only the semantic just rescored; unrelated fresh-cohort
variance cannot overwrite unswept entries. Generation 27151 did enter this sweep at
179/198 = 90.404%. Its first `C.COUNT` rescore moved 32/33 to 31/33 with zero retained
optimizer updates, which alone would move the running mean to 178/198 = 89.899% and
correctly abort. The old implementation additionally replaced all other C scores from
the new cohort, exaggerating that apparent drop to 84.848%. Resume preflight at the
current generation reports no blockers, no migration, and zero neural updates.

---

# Issue349 handoff | 2026-10-22 | COUNT opens NUMBER

## Read this first: the user's controlling course

**Teach concepts through fundamentals already expressible by prior understanding.**
The course is **logic and basic cognitive algebra → mathematics → physics**, with
selective New Ithkuil Lexicon **Chapters2,3,6** supplying concepts as their
constituents become available. A “narrow staircase built exclusively upon its
foundations” must appear in actual lesson construction, not just prerequisite labels.
**We are not building tiny world models at this stage.** Event lookup, before/after
classification and larger distractor worlds were an experimental detour. Preserve
their evidence; do not resume them as the next curriculum.

**NOT and AND may be introduced, but mastery of them must not gate Grade C.**
The user explicitly authorized that progression. C keeps its designed numeric
prerequisites and stages. Carry unresolved A/B debt; do not fabricate graduation
or add a blanket perfect-school gate. ADR-087/088 record these decisions. AGENTS.md
and README.md lead with the same direction. Earlier D–O and event-first plans are
historical research, not current sequencing authority.

## Current branch and stopped student

Branch `codex/349-autonomous-jit-ithkuil-20261020`; [draft PR11](https://github.com/Entif-AI/Bilqis-MLX/pull/11).
Managed worktree `/Users/emilie/Code/.worktrees/Bilqis-MLX/349-autonomous-jit-ithkuil-20261020`.
Main `025bca51c78509acd0b1b898f16e9fcf84d25941` is integrated through staging
`94c2e500523b45472ee257cf4021730309f5b848`, including the B-stagnation fix and DAG
retry correction. Read actual HEAD/PR for the final merge SHA. Feature preservation
ref: `codex/349-before-premerge-20261022` at b73f47e.
IPR-0220 remediation and execution authorities remain relevant; when authorized, read their protected current
checkpoints before changing semantics or custody. Issue346 remains excluded.
**Bilqis-MLX and its implementation are public.** Publish repository-owned code, tests, architecture, and ordinary handoffs directly; keep private-only source text, credentials, attachments, and protected repository URLs out of tracked public artifacts unless separately released.

Selected run: `runs/issue-349-experiments/primary`, generation **492**.
Native step **117296**, student + own AdamW SHA
`756061ff78f931be96987af430fbc16dbca66f476d00c8c9ea67d30811387a2a`,
bundle `bundles/working-190-4316e72c43f8`.
Executable release `48bde559d301964ee012acd48e2606ac0e7dc725f52d22032afac65427ec454e`.
Both issue runs are stopped; operator locks were checked. No canonical/historical
run was modified, no student reset, third lineage or AdamW merge occurred.

Active grades **A+B+C**. B exposes only **NOT/AND**. C exposes COUNT → NUMBER →
SUCCESSOR → ADD → SUB at **0..3**, with persisted final ceiling **4**; MUL/DIV are
not enabled. **COUNT and NUMBER are introduced**, introduction_stage1, queue C.NUMBER,
RECOVERY_1. A perfect COUNT routine panel opened NUMBER through the existing stage
rule. SUCCESSOR and later stages await C's own constituent criteria, not B mastery.
All six A capabilities plus B.NOT/B.AND remain carried mastery debt.

## Current software integration (no new learning)

The pre-merge packet's storage, performance, weakness-target, no-gain, mean-promotion
and earlier-grade spiral behavior is ported into the extracted owners. `trainer.py`
remains a 307-line compatibility facade. Pure promotion invariants live beside the
scheduler in `curriculum/promotion.py`; size/error ratchets remain active.

Known A/B/C automatic debt transitions remeasure exact checkpoint boundaries,
retain thin NOT/AND and saved numeric ceiling4. Unsupported JIT grades keep their
existing complete-prefix/factory gate. B stays measured and taught but cannot
actuate quarantine or a stagnation-review exit; C containment stays independent.
Incoming ADR083–086 keep their IDs; feature foundations083→087 and Boolean
non-gating084→088, with provenance recorded in ADR.md. Earlier receipts retain
source-local historical references.

An additional red/green test caught orphan DAG recovery from a verified legacy
JSON head. The retry path now accepts only identical immutable receipts linked
to the verified current legacy generation or its direct successor; changed or
stale receipts still fail closed. No run history was rewritten.

Read-only actual primary `_resume` passed at492/117296 with the entire logical
receipt unchanged. Publication failed closed and stale-soup retirement was
disabled for that protocol; this is not a normal writable-resume/cleanup trial.
No --human-run, experimental/canonical neural update, optimizer reset or new
lineage was launched during integration. **Current validation:1,276 passed /41 skipped /0 failed**, plus final56/56
focused checks after the saved-profile resume extraction. Architecture/size/docs/
error-plane/code-smell guards pass; external ABI enforcement remains advisory.
This supersedes the prior wave's red-suite status below; its failure logs remain
historical. [Integration receipt](docs/evidence/development/ISSUE349_MAIN_INTEGRATION_20261022.md)
records limits. Prior learning observations below remain historical evidence.

## Latest continuation: actual learning, no product-code changes

Three further bounded commands stopped normally: **34 optimizer visits /1,088
attempted updates /192 retained** (COUNT160, NUMBER32). Two perfect-target visits
were skipped. No teacher policy, retention threshold, generator or release changed.
The third command retained zero updates: NUMBER candidates either failed to improve
the target or regressed the same-grade panel. Preserve this plateau as evidence.

On the same seeded panel, COUNT **154/180 →178/180 →180/180**; direct numbers
**56/60→60/60**, equality **98/120→120/120**. These180 rows contain **27 unique
input token sequences:20/27→26/27→27/27**. NUMBER is **165/180**, representing
**11/12 unique inputs**. Its one error is literal3→2; all120 equality rows pass.
NUMBER currently presents a literal numeral and equality true/false contrasts;
COUNT presents visible finite sets. This is finite0..3 symbol learning, not broad
number understanding or unexposed generalization. Exposure overlap NOT_MEASURED.

Final seeded A: IDENTITY86/113, PARENT72/132, LINK73/147, MEMBER66/121,
EDGE80/142, MAPS70/139. B.NOT100/180 and B.AND90/180 remain debt. SUCCESSOR,
ADD and SUB have not been introduced. No graduation is claimed.

Actual final cold `_resume` at492/117296 preserved the **entire logical state** and
native optimizer step. Both operator locks checked; preserved event control still
676/119940/9f5b196a. Current measured collective use **18,153,443,328 bytes**.

Receipt: `docs/evidence/experiments/20261022-issue349-count-to-number.json`.
Raw probes, scripts and cold-resume readback: `.local/issue349-count-continuation/`.
The receipt binds exact logs, checkpoints, per-phase decisions and unique-input
counts. Prior full-suite/storage limitations and incidents below remain unchanged.

## Prior wave observations (historical generation421)

Four bounded commands: **34 optimizer visits / 1,088 attempted updates / 288 retained**.
A repair retained64; the two Boolean introductions retained32 (AND); C.COUNT
retained192 across24 visits. No new-grade admission performed an optimizer update.

On the **same180 seeded COUNT questions**, the preserved pre-C-teaching checkpoint
scored **69/180**, versus **154/180** at the final checkpoint:

- Direct numeric cardinality: **15/60 → 56/60**.
- Equality true/false contrast views: **54/120 → 98/120**.

The second C pass alone moved the panel138/180→154/180. Final routine COUNT is
**28/33**. Final seeded B.NOT is91/180 and B.AND95/180; neither is mastered and
neither blocked C. Earlier A skills remain uneven. These are finite0..3 symbolic
set-cardinality results. Training-exposure overlap is **NOT_MEASURED**; new seeds
do not establish unexposed generalization, complete concepts or grade graduation.

Actual COUNT input is a typed finite set, e.g. COUNT({0,1})→2; the same construction
also offers EQ(COUNT({0,1}),2)→TRUE and a source-valid wrong-number contrast→FALSE.
The set members are visible in input. It adds no event or physical-world semantics.
Keep using `numeric_curriculum`/the typed AST and independent oracle; do not invent
new root-specific trainers or increase scope to make the result look stronger.

Receipt: `docs/evidence/experiments/20261022-issue349-foundations-through-counting.json`.
Raw local admissions, recovery and paired probes: `.local/issue349-debt-continuation/`.
The earlier `20261022-issue349-foundation-realignment.json` is the historical
pre-adoption selection, not current state.

## Prior implementation and verification

The compatibility Course view can project a legal thin Boolean roster, and legacy
resume defaults no longer replace this selection with AND/IFF. Numeric entry
preserves the admitted Boolean profile. Same-ABI next-grade admission explicitly
reuses complete exact-checkpoint boundary measurement + debt custody; ordinary
append still requires its existing graduated boundary. Debt is an explicit caller
choice, never inferred from an omitted option.

A real first B resume exposed dropped cohort schema. Routine exams now preserve
the complete cohort pointer; debt receipts keep their separate `boundary_schema`.
Debt profile admission retains the fresh verified predecessor boundary. Strict
release/source/student guards remain. Generation365 was preserved; generation366
appended a newly source-scored A+B boundary at the unchanged checkpoint before
normal training resumed. No historical scores or checkpoints were rewritten.

Actual cold `_resume` also verified the complete saved state at historical generation421 /
step117104 without any logical receipt change or optimizer update.

**41 focused tests pass**, including real-provider A→thinB→C with unresolved
NOT/AND, stale-boundary rejection, cold cohort verification after both transitions,
and the actual toy A teaching/exam path. Architecture/docs/error-plane/size checks
pass. ABI remains advisory without an independent expected digest. Broader legacy
A/C storage tests are **not green**: raw Merkle-pointer readers, pre-C recovery and
diagnostic readback failed in logs09-59-49-507Z-49026,10-01-36-963Z-80273 and
10-03-12-121Z-580. Only the affected A end-to-end test reader was updated; do not
claim the entire storage migration or full suite is repaired. The extra factory
closure check's two inherited numeric-provider imports remain prior recorded debt.

PM-2026-10-22-005 (selection drift, RC-047/RC-096, PAT-076) and
PM-2026-10-20-003 / RC-116 (producer/consumer schema propagation) were enriched
and exact native Sheet readbacks verified. Preserve their separate meanings.

## Next permitted action

Continue from NUMBER, inspecting its literal3→2 error and delivered teacher
strategies. The latest12 NUMBER attempts retained nothing; prefer a small useful
trial informed by those receipts over blindly enlarging scope. Let existing C
stages progress on their own evidence. Keep
NOT/AND and earlier A mistakes in debt/rehearsal. No event-control resume, new
qualification framework, teacher-policy override or invented Boolean prerequisite.

```sh
cd /Users/emilie/Code/.worktrees/Bilqis-MLX/349-autonomous-jit-ithkuil-20261020
export BILQIS_DATA_PLANE="$PWD/runs/issue-349-experiments/primary/data-plane.sqlite3"
export BILQIS_INTEGER_MAX=4
python3 -B -m bilqis_mlx.cli train --human-run --resume \
  --run-dir "$PWD/runs/issue-349-experiments/primary" \
  --issue-349-experiment-root "$PWD/runs/issue-349-experiments" \
  --minutes 4 --max-visits 12 --steps-per-visit 32 --source-prefetch-workers 0
```

The saved numeric profile/ceiling survives resume; no new admission flag is needed.
Before any continuation inspect current state/lock and remeasure the collective
budget through `ExperimentRunBudget`. Use `state_dag.read_current` or
`read_current_fields`, not raw state.json. The counted SQLite/WAL is durable run
state; never delete it independently of its heads. Never use --no-retention here.

The preserved event control remains generation676 / step119940 / SHA
`9f5b196a559929a211ce10e1878def3ac89b5222dc6eee4c47085d4bf00c525a`.
It has its **own** data plane under plasticity-control, which must be selected for
any read of that run. Exactly two registered directories measure
**18,153,443,328 allocated bytes /100,000,000,000**. Keep both current
students and required recovery evidence. Do not merge main or close the execution issue.
