# Grade B source constructors and human-operated MLX continuation

**Private implementation | ADR-025 | 2026-10-15 | Scope: first Boolean composition only**

## Source and authority

The controlling user direction permits continuing the engineering work without another question. Real model updates remain the human operator's exclusive action. Original source authorities are `../bilqis-triplets-v16/bilqis_logic/kernel.py` (Boolean AST/`TABLES`/two-variable codec) and `../bilqis-triplets-v16/bilqis_micro/kernel.py` (micro-world syntax, recursive operation evaluator and independent truth-table evaluator). The pinned Boolean source SHA-256 is `9b73993d042cebb9d46656884966ca92b024fccdd0d32e89b0071b0718fb2c6c`. Runtime `grade_a_probe.read_sources()` verifies the original graph/prefix and historical source digests; `live_grade_b.source_attestation()` rechecks the Boolean source and the operator and operand token names. No source tree, old graph, or original model is rewritten.

All six admitted operators already have original `cogal.operator.*` token identities. Their operands use `micro.compare.EQ`, `micro.relation.PARENT`, and `micro.relation.LINK`, with prerequisites `A.IDENTITY`, `A.PARENT`, and `A.LINK` respectively. These are typed finite-world formal semantics. Official New Ithkuil lexical correspondence is research cartography only: the adjudication in `NI_SEMANTIC_ADJUDICATION_VD_20261015.md` explicitly does **not** identify any such Boolean operator as automatically equivalent to an inflected New Ithkuil form. No NI morphological or lexical release is claimed here.

| Current grade B capability | Formal truth condition |
|---|---|
| `B.NOT` | Negate one source predicate |
| `B.AND` | Both source predicates true |
| `B.OR` | At least one source predicate true |
| `B.XOR` | Exactly one source predicate true |
| `B.IMPLIES` | False only when antecedent true and consequent false |
| `B.IFF` | Source predicate truth values equal |

These six are one bounded tier of direct Boolean composition, not a claim that the learner has acquired numeric/cardinality outputs, set-theoretic constructors, graph traversal, New Ithkuil legal wordforms, or all future logical semantic functions. The original `B01..B07` labels are archival aliases, not this new letter-grade admission.

## Executable proof

`bilqis_mlx/live_grade_b.py` binds the original Grade A six-capability rubric unchanged, materializes a complete independently checked B witness before release, and admits six B capabilities with twelve dynamically sampled, balanced binary questions each. Source interpreter `bilqis_micro.kernel.evaluate`, distinct original `independent_evaluate`, and `bilqis_mlx/grade_b_oracle.evaluate` must all agree. The third oracle interprets the serialized world, direct EQ/PARENT/LINK facts, and explicit Boolean conditions without calling either source interpreter or the student's predictions. Constructor code/source SHA, stable cumulative A+B rubric, question seed, and complete cohort content digest are recorded separately. Every exam's B set contains both true and false constructions, three- and four-element worlds, and exactly twelve cases per admitted B capability. Nothing is permanently hidden from later instruction.

The resulting A+B course contains twelve total capabilities and a freshly generated **144-question** cumulative rubric. Scoring requires one complete checkpoint for all 144, never a collage of per-capability student weights. An initial 72/72 B result initiates ADR-024 A→B backward revalidation. Before a future Grade C is admitted, the final A+B checkpoint must be perfect across *both* grades at once. The complete candidate/incumbent comparison is on the same content-addressed sampled cohort, not different random questions.

The active human-run `grade_a_trainer.operate()` code can resume the existing qualified A student into B under the *same* explicit user terminal command. It reuses the full FP32 model, matching own AdamW, inherited teacher policy and observations, exactly 222 preserved token IDs, historical A champion, and the previous immutable state generations. Frozen prior-grade champion models may cast votes on which oracle-verified teaching examples to prioritize. Votes are one per represented grade even if several grade pointers share one checkpoint. They never become substitute oracle labels, unsound synthetic student weights, or cross-cohort exam comparisons. The existing staging, quarantine, disk reserve, exclusive operator lock, event ledger and six School50 panels remain in force. `npm run train -- --dry-run --resume` source-checks and announces the intended next admission without neural updates.

The immutable `delivery_outbox` in each newly committed generation records the intended initializer, A→B admission, visited capability lessons, scorer events and checkpoint-best announcements before it publishes the latest state pointer. Missing journal events are replayed by exact source/lineage-bound IDs after restart; fsynced earlier entries are not duplicated. This covers the previously discovered crash gap between a complete saved student and its telemetry. A taught A capability during B's weakest-three recovery updates the A teacher grade statistics, with B retained as the distinct active scheduling grade. The dashboard summary selects the grade whose assessment completed, not the last letter alphabetically represented in the full cumulative score table.

## Evidence and limitations

Tests in `tests/test_live_grade_b.py` require exact source/graph identity, constructor and oracle agreement, balanced 72-item B source cohorts, sample rotation and tamper rejection. `tests/test_grade_b_trainer.py` checks immutable A→B saved-state migration with unchanged student/optimizer/teacher pointers, interrupted state-pointer and event publication recovery with exactly-once readback, ledger tamper detection, per-capability grade credit, preserved A and B cohort hashes, source-gold-only champion votes, and a full disposable MLX B→A→B 144-item examination progression. The latter uses toy trainable tensors and explicitly mocked correct predictions for its graduation transitions: it verifies pipeline mechanics and *does not* measure actual student acquisition. Historical Grade A test receipts remain immutable, and human model optimizer step 153144 remains the live observed pre-B boundary.

**Not yet measured:** any genuine human-trained B score, B learning curve, persistence of A competencies under real B updates, full-program New Ithkuil completion, numeric/native-token output admission, and exact NI morphological conformance. No agent invokes `--human-run`. Grade C and later syllabi need their own independent source+prerequisite+admission releases.

## 2026-10-16 human-run correction: observed regression, not sealed exams

This document originally described a pre-run implementation. Real operator
training has now exposed weak B acquisition and rapid A forgetting. The
human student scored 55/72 A and 33/72 B at step 155640, against its original
retained Grade A champion's 71/72 A and 39/72 B on **the identical sampled
cohort**. No permanent Grade B sealed-question embargo exists, but each new
exam previously discarded the whole previous mistake queue. The second
weakest-three round also excluded first-round members even when still worst.

ADR-026 originally proposed retaining a fixed-size still-incorrect mistake
backlog, reranking the full eligible pool, and inserting up to one-quarter
source-oracled A operand micro-lessons in B batches. The fixed-size quota and
injection were later retired under ADR-031. Current fair replay tracks actual
exposure and uses available batch answer classes while the inherited teacher
retains its policy selection; exams reveal no gold during scoring. See
`docs/evidence/diagnostics/GRADE_B_REGRESSION_FORENSICS_20261016.md` for the measured failure
and verification limits. Software regressions pass; actual recovery remains
untested until a human deliberately runs and measures the intact student.
