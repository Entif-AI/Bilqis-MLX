# School50 telemetry v1: six panels across all letter grades

The human operator requested the old dashboard's diagnostic depth back,
without rebuilding it at each future letter-grade admission. This is a
**read-only visualization contract**, not a neural training protocol, grade
admission decision, or substitute for independently verified examinations.

## Stable schema and adapters

Producer contract: `bilqis.school50.telemetry/v1`, implemented by
`bilqis_mlx/school_telemetry.py`. The original `spiral_dashboard.py` retains
its legacy six-panel names, source-event behavior, and public `TABLES`
definition; the letter school supplies separate `LETTER_TABLES` columns.
The existing `GRADE_A_*` committed events are normalized to the same
projection. Future B/C/... writers can emit **grade-neutral** `SCHOOL_*`
events with a `grade` field instead of requiring another Grade B dashboard.
If `telemetry_schema` is present, it must exactly match the v1 identifier.

Event families and grounded field requirements:

| Event | Purpose / fields | Pane |
| --- | --- | --- |
| `SCHOOL_RUN_INITIALIZED` | Source/model starting step | System and headline |
| `SCHOOL_VISIT_COMMITTED` | `grade`, `capability`, `optimizer_step`, source-training accuracy before/after, strategy, policy identity, loss, gradient norm, teacher reward; optional `instruction_method`, earlier-grade pp delta | Candidates; Soup & Teacher |
| `SCHOOL_EXAM_COMMITTED` | `grade`, versioned `rubric`, **one** `student_sha256` and `optimizer_step`, typed `scores` by capability with matching model identity | Bridge Families; Grades & Mastery; exam-to-exam retention |
| `SCHOOL_SENTINEL_COMMITTED` | `grade`, `partition: independent_validation`, `dataset_sha256`, `student_sha256`, `optimizer_step`; genuine measured probe/worst/sentinel percentage-point deltas and optional cross-entropy, correct-probability and margin deltas | Sentinel & Retention |
| `SCHOOL_FAMILY_PROBE_COMMITTED` | `grade`, `family`, `partition`, source dataset/model fingerprints, step, typed before/after counts on same underlying probe | Bridge Families; never qualification |
| `SCHOOL_SOUP_COMMITTED` | `grade`, `teacher_only: true`, stable `teacher_digest`; optional soup/parent KL, supervised CE, coverage, bridge CE, teacher credit | Soup & Teacher |
| `SCHOOL_RESOURCE_OBSERVED` | `grade`, actual disk `free_bytes`, protected `reserve_bytes`, next write `estimated_write_bytes` | System & Qualification |
| `SCHOOL_QUALIFICATION_COMMITTED` | `grade`, recorded status and source-linked details; **presentation only** | System & Qualification |
| `SCHOOL_SESSION_STOPPED` | Cause, time, completed visits and optimizer step | System and footer |

The existing historical `GRADE_A_TEACHER_VISIT_COMMITTED`,
`GRADE_A_EXAM_COMMITTED`, `GRADE_A_NEW_RUN_INITIALIZED` and
`GRADE_A_SESSION_STOPPED` remain supported unchanged. No new event family is
silently added to the live trainer by this work; later grade producers must
actually measure and write their proposed evidence fields.

## Measurement definitions

**First, latest, best, and TO100** are taken from actual sealed examination
receipts. Their aggregation key includes **grade and exact complete rubric**;
the display never fuses independent checkpoints into one "perfect" student.
An A+B cumulative examination may report both grade A and grade B capability
scores at one common whole-student checkpoint. An earlier A-only exam is not
numerically compared as equivalent to a subsequently revised cumulative
rubric unless rubric identity is preserved. "Best" is a historical
observation and is labeled with its *own* checkpoint step, never a current
model or synthetic candidate.

**Bridge Families** shows first/previous/latest correct counts and gain per
distinct capability from matching sealed examination rubrics, or from
separately identified, source-attested family-probe events. A predicted gain
is not evidence. **Exam pp and worst pp** are differences between consecutive
completed exams on the same rubric. They are not independent sentinel
measurements or training rewards.

**Source-train reward** remains in-sample capability improvement. The
dashboard can identify an *observed generalization gap* when all capabilities
in a recent sealed exam were also recently near-perfect on their own
instructional examples, yet sealed grade accuracy is below 100%. These
instructional observations may come from **different steps**, and the
diagnostic is never used to update the actual optimizer or adaptive teacher.

**Unavailable measurements remain unavailable.** Grade A currently lacks a
separate independent sentinel, meaningful cross-grade distillation, numeric
answer coverage, mixed-grade soup, and legacy School50's optional correct-
probability, margin and cross-entropy changes. Do not fill those cells with
Grade A training scores or exam accuracy. Policy fields `old`, `preview`
and `distill` explicitly display `OFF` when the trainer reports them inactive.
Future grades may make them meaningful *only with actual logged evidence*.
Validated provenance is necessary for independent sentinel and family probe
records. The dashboard verifies supplied hashes' shapes and coherence; it
does **not** independently audit dataset disjointness or certify the metric's
statistical validity. Source evaluation and admission remain separate gates.

**Historical champions vs current regression:** a saved champion remains a
retained pointer. A current cumulative exam with subperfect performance
reports CURRENT REGRESSION rather than silently replacing or denying that
earlier champion. The persisted school scheduler, not this visualization,
is the authority for mastery and promotion.

## Behavior and extensibility

`npm run dashboard` replays committed events **without writing** to the
model, optimizer, teacher or event log. Replay is streamed line by line and
visual row history remains bounded. It can inspect a currently running
human-owned session, though a process already running the former dashboard
code cannot hot-load these display changes. On the **next operator-owned
invocation**, the six panels upgrade automatically in the same terminal.

**Storage is an operational metric, not an automatic reclaim policy.** The
read-only dashboard reports actual free space against the configured/default
reserve plus estimated next bundle size, with `READY` or `BLOCKED` status.
When this preflight cannot reserve the next model/AdamW checkpoint, the
trainer now emits `DISK_RESERVE_REACHED` as a normal, durable, legible stop
reason, with byte-exact disk evidence. Do not silently reduce reserves,
delete prior complete bundles, skip mandated checkpoints or reinterpret a
free-space block as neural mastery. A hard budget failure between the check
and a bundle write remains fail-closed and may require resume from the prior
fully committed student. The disk guard never modifies optimizer data.

The first human no-visit-cap continuation stopped near saved generation
1242/visit 993 with about 100.28 GiB available against **100 GiB reserve +
600 MB next-visit allowance**. The existing final exam remained 36/72.
That historical run has no normal-stop receipt because the earlier code
raised `DISK_BUDGET_EXHAUSTED` outside the normal termination path; the next
version explicitly reports this cause. These are read-only measurements,
not an instruction to remove historical checkpoints.

Tests in `tests/test_letter_school_telemetry.py` cover old/future events,
two-grade same-checkpoint exams, arithmetic first/latest/best/gain/TO100,
real source-training policy and gradient signals, independent sentinel and
teacher-only soup evidence, missing/fake metrics, persisted champion vs
current grade results, and the original 276-column wide terminal layout.
The legacy dashboard and Grade A source-training assessment contracts are
not altered.

Future lesson/probe constructors should reference the Curriculum AST's
semantic and prerequisite nodes, emit versioned event family identities,
and bind both a *source partition* and *whole-student checkpoint*. Merely
generating more questions or adding a new grade letter is not evidence of
independent semantic generalization.
