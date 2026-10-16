# Bilqis MLX: private, independent successor

**Vocabulary-size authority (ADR-030):** The original complete student's model ABI is declared once by [`bilqis_mlx/semantics/legacy_abi_v1.json`](bilqis_mlx/semantics/legacy_abi_v1.json). Import `HISTORICAL_PREFIX_SIZE` from [`bilqis_mlx.semantics.abi`](bilqis_mlx/semantics/abi.py) for historical checkpoint/index compatibility. An admitted **current** model's vocabulary length comes from its versioned graph/catalog, not from the old prefix as a ceiling. The [ABI/merge guard](docs/architecture/09_HISTORICAL_ABI_AND_MERGE_CHECK.md) checks exact historical semantic fields and separately controlled expected evidence; numeric counts in dated results below are frozen observations, not independent configuration knobs. New grade admission and actual training remain separately governed.

**State: Source-generated six-capability Grade A instruction and rotating 72-item assessments are wired for human-operated training. Historical 144+72 records remain immutable evidence; agents never train the actual student.**

This private repository implements the successor directed by protected IPR-0220. Its public interoperability-facing summaries are Bilqis #160 (MLX backend qualification) and #162 (successor integration). The detailed internal curriculum, promotion and resource policy stays private.

**Founding premise:** Bilqis learns a deliberately defined shared pasigraphy, not an opaque tokenizer that we attempt to interpret afterward. Each token is a stable, individually interpretable semantic identity or function, registered one-to-one in the canonical curriculum spreadsheet. Composite meanings use **multiple known tokens** assembled according to faithfully implemented New Ithkuil lexicon, morphology and grammar rules. The training regimen itself is a progressively expanding conformance test suite for that language, intended to give different AI systems and human oversight specialists a common, inspectable lingua franca. This cataloging contract holds for every learned token until at least completion of the New Ithkuil course; future freedom beyond our dialect is a separately governed transition. See [foundational pasigraphy contract](docs/PASIGRAPHY_TOKEN_CONTRACT_20261015.md).

**Living catalog:** models pin their approved semantic ABI while spreadsheet descriptions and New Ithkuil correspondences evolve. Propose, review, approve and version changes; never discard learned weights due to an editorial update. Search the official Ithkuil grammar and lexicon before inventing roots. See [the living-ledger policy](docs/LIVING_PASIGRAPHY_LEDGER_20261015.md).

For the historical 222-token New Ithkuil crosswalk, the user delegated semantic-review decisions to the assistant (protected IPR-0220 comment `6187168824`). Any approved version must distinguish exact, qualified, compositional, native protocol and unresolved relationships; it does not certify an executable New Ithkuil wordform or neural learning.

The current native ledger successor `mapping-review/20261015-d` has 222/222 explicit reviewed semantic classifications and preserves the predecessor in `Token Mapping Reviews vC Snapshot`. Its 94 newly adjudicated tokens are individually documented in [the source-checked NI adjudication](docs/NI_SEMANTIC_ADJUDICATION_VD_20261015.md); no New Ithkuil surface wordforms or student language competence are certified. The prior model remains pinned to `legacy-source/v1`. Formal composition, grammar, and proficiency testing remain ahead, not silently passed.

The [first executable NI construction slice](docs/NI_CONSTRUCTION_SCOPE_20261015.md) handles 0..100 numerals with TNX, THM/PAR, optional shortcut morphology, and simple neutral monadic referentials. `python3 -m bilqis_mlx.ni_construction number 42` produces a source-linked analysis; `python3 -m bilqis_mlx.ni_construction parse-number ksalirsa` reverses it. `python3 -m bilqis_mlx.ni_construction_audit` emits 101 historical-token-indexed research rows. Only five numerical wordforms are literal Ch.13 witnesses; others are rule-derived and remain independently uncertified. This adds no learned tokens, lessons, or neural updates.

The prior 29 `G##` units are **capabilities**. This new school uses lettered **grades** (A, B, C...) with about six to nine prerequisite-compatible capabilities per grade. A run starts with grade A unless the operator explicitly supplies `--resume`. A grade is mastered only by one complete candidate model and its *own* optimizer scoring 100% on all that grade's tests at the same checkpoint. Past grade champions vote once *per represented grade*, even when multiple pointers share one physical checkpoint. Weighted whole-school soup makes a teacher only, never a synthetic trainable student. **ADR-024 adds cumulative grade revalidation:** after first mastering B, the scheduler revisits A then B before C; after C, it revisits A, B and C before D, continuing this pattern for each new grade. Each replay uses the same full-grade pass and, when mastery remains incomplete, two freshly ranked weakest-three recovery rounds. A partial program cannot advance to the next grade until a complete same-checkpoint assessment of the whole known prefix is perfect. Original grade champions remain protected during regressions; Grade B's subsequently implemented source admission is described under ADR-025.

Read [whole-student MLX parity evidence](docs/MLX_FULL_STUDENT_PARITY_20261015.md) and [Grade A source audit](docs/GRADE_A_SOURCE_AUDIT.md) before suggesting training.

Development rules: do not invent untaught roots, do not examine composed semantics before mastered constituents, and do not inherit the historic 1,150-question exam as the new graduation rule. Preserve the old entire FP32 checkpoint and its AdamW. MLX conversion is fail-closed until actual full-state parity is proven.

## Operator interface

Run from this repository:

```sh
npm run status
npm run dashboard
npm run train -- --dry-run --verify-source
npm run train -- --human-run --minutes 90
# Resume the same intact saved student (Grade B follows A mastery automatically):
npm run train -- --human-run --resume --minutes 90
```

**Current live contract (ADR-022/023):** This same human-run command automatically executes the generated Grade A curriculum. Each of the six admitted predicates receives newly constructed, three-oracle-checked instruction on every visit and every optimizer batch. Each due exam samples a reproducible fresh 72-item cohort (12 per capability, balanced TRUE/FALSE and attested world sizes). All current and historical whole-student leaders are replayed on **that same cohort** before best-score promotion; its SHA, source IDs, misses and comparator receipts persist. Every exam miss becomes eligible for subsequent teacher instruction, with no permanent holdout embargo. The 144 historical teaching records and original fixed 72 exam questions remain unchanged as archival evidence. Legacy `--resume` migrates its saved state automatically while preserving the FP32 model, own AdamW, teacher history and old receipts. Grade A still requires 72/72 on one complete sampled cohort at the same model checkpoint. There is no activation flag beyond `--human-run` and `--resume` as applicable. Typed numeric/native-token training exists separately as a tested research adapter; it has not been admitted into these six Boolean Grade A capabilities.

**Current Grade B successor (ADR-025):** Grade A is now human-mastered at 72/72; its complete student, own AdamW, 222-token graph and inherited teacher are preserved. On the human's explicit `--resume` from an A `AWAITING_NEXT_GRADE` checkpoint, source verification automatically admits the six next similarly scoped typed formal operators `B.NOT`, `B.AND`, `B.OR`, `B.XOR`, `B.IMPLIES` and `B.IFF`. Their operands use only already-taught `A.IDENTITY`, `A.PARENT`, and `A.LINK` semantics and original token IDs. New source-oracled, dynamically varied lessons cover each visit and optimizer step, with positive/negative cases; three independently agreeing evaluators verify every gold. The next cumulative examination samples **144 items** (12 per capability across A+B) at one full checkpoint, compares challenger and incumbents on exactly that cohort, and requires B=12/12 for all its capabilities. Per ADR-024 the first B graduation triggers full A→B revalidation; the final B sweep checkpoint must pass **all 144/144** before Grade C is permitted. Previous A and B champions cast one curriculum-example vote per represented grade, even if sharing a checkpoint; golds remain oracle-owned. This is a private **typed logical adapter**, not a claim of compiled New Ithkuil inflections or mastered natural-language grammar. **Only the human may invoke neural training; Grade B has no real-student convergence result yet.** The neural-inert `npm run train -- --dry-run --resume` shows the planned admission and exact rubric before any user-initiated run. See [Grade B verified source and adoption](docs/GRADE_B_LIVE_CONSTRUCTORS_20261015.md).

**Crash-safe event custody (ADR-025):** Each newly committed training generation includes an immutable outbox of its own initialization, visits, capability-best promotions, sampled exam/comparison, or A→B admission events. If JSONL publication is interrupted after the full student+AdamW/state commit, the next human resume reconciles missing event IDs from that exact generation; events already fsynced are not duplicated, and mismatched content fails closed. The next scheduled grade is reported separately from the grade whose lesson or exam just completed.

**Grade B live-learning correction (ADR-026, 2026-10-16):** The real human Grade B session exposed a serious regression, **not** a hidden sealed-exam partition. Matched-cohort results at optimizer step 155640 show current A 55/72 and B 33/72 against frozen Grade A champion A 71/72 and B 39/72 on the very same 144 sampled questions. Previously, every exam discarded old failed teaching examples even when their capabilities had received no intervening visit; the second weakest-three pass also wrongfully excluded the first trio. The trainer now carries still-wrong source-verified misses into future lessons with a bounded per-capability queue, re-ranks *all* eligible capabilities anew for each recovery round, and teaches individually oracle-verified A operand questions directly alongside dynamically sampled B compositions (at most 25% of each B batch). No permanent examples are forbidden, no grade or rubric is relaxed, no historical checkpoint reset occurred, and actual learning recovery **remains unmeasured**. See [Grade B live-run regression forensics](docs/GRADE_B_REGRESSION_FORENSICS_20261016.md). Only human invocation of `--human-run` can collect new neural evidence.

Historical sections below describe the predecessor sealed-exam policy and should be read as source-lineage evidence where they mention frozen Grade A as the active examination.

`status`, `dashboard` and `--dry-run` are neural-inert. `npm run dashboard` **replays the saved event ledger and displays the latest six-panel School50 snapshot even after training stops**. A human training command on an interactive terminal presents the same dashboard **in that terminal**, redrawing at each durably committed assessment or operator-stop boundary (intermediate visits are provisional under ADR-018). At normal exit it now announces and records the exact reason for stopping, including elapsed time, visits and optimizer step. Non-TTY runs retain JSON event output with a terminal stop receipt. **Actual student training requires the human to supply `--human-run`**. A run with existing saved content must use `--resume`; omitting it deliberately blocks a fresh start and prints the safe resume command. The default is 90 minutes, **no hidden visit cap** and 16 optimizer steps per visit. Use `--max-visits N` only if an explicit earlier stop is desired; the 100 GiB disk reserve remains in force. Due grade exams finish before a normal stop. Interruptions recover the last *committed* complete student plus its own AdamW, without reinterpreting `--resume` as the old G12 curriculum. Check `npm run status` for current grade, phase, student SHA, optimizer step, teacher events and most recent complete stop reason.

The **restored six-panel diagnostic projection** now distinguishes instructional accuracy/reward from fixed held-out examination results; shows first/latest/best exams and TO100, real loss/gradient and teacher policy, per-capability gains and regressions, and optional future evidence-bound sentinel, semantic probe and teacher-only soup metrics. The existing old dashboard renderer continues to work. New grade writers use the shared `bilqis.school50.telemetry/v1` events with no Grade B/C special-case dashboard. Missing measurements are explicitly NOT MEASURED, never guessed. The full measurement/source/checkpoint contract is in [School50 telemetry](docs/SCHOOL50_TELEMETRY_V1_20261015.md). A human trainer already running an earlier code version will not hot-reload these improvements; its next invocation inherits them while `npm run dashboard` can read its existing saved events safely at any time.

**Mandatory PyTorch curriculum inheritance (ADR-019):** The original v10 School50 B curriculum already taught four-way direct numeric answers alongside five-state evidence and deliberately repeated exact taught questions before testing transfer. The accepted MLX Grade A currently supplies only binary answers, which is not pedagogical parity. The read-only `npm run curriculum:parity` reproduces original oracle-defined direct/TRUE/FALSE/negative pairs, correct 12/4/4 arithmetic source ownership, exact acquisition replay, and three historical 48-row instructional methods; its disposable MLX mixed-caste readout uses the actual pinned 222-token embedding catalog. [The parity audit](docs/PYTORCH_TO_MLX_PEDAGOGY_PARITY_20261015.md) records the remaining typed constructions, prerequisite and independent-exam release gates. The current frozen Grade A remains unchanged, and **parity research does not authorize training**.

**Output vocabulary correction (ADR-020):** The source-backed parity proposal now trains native `school.number.N` output-token selection over the *entire* current model vocabulary alongside the restricted four-way numeric exercise and separate five-state evidence assertions. The full-vocabulary loss is real supervision, not a printed label or 101-number-only diagnostic; the head must grow with future admitted catalog tokens. This remains a research-only **single-token** answer construction, not an activated curriculum or an arbitrary multi-token New Ithkuil decoder.

**Typed integer scope and on-demand generated tests (ADR-021):** Set a single `BILQIS_INTEGER_MAX=3` in the local ignored `.env` (start from `.env.example`). Changing it to `9` expands newly generated training exercises to integer operands, intermediate values and answers `0..9`; the full semantic-token vocabulary remains intact. The tests do *not* auto-regenerate: run `npm run curriculum:tests -- --plan-tests=type:integer`, then `npm run curriculum:tests -- --regenerate-tests=type:integer`, then `npm run curriculum:tests -- --check-tests=type:integer`. Type dependencies rebuild direct Number outputs, derived Boolean comparisons, equivalence and negation suites together, leaving unrelated tests untouched. The old generated release is preserved, while a stale integer limit fails validation. These are research-only generated tests, separate from the frozen Grade A exam. Full details in [the generated integer-test contract](docs/TYPED_INTEGER_GENERATED_TESTS_20261015.md).

**Disk protection is visible:** the System panel reports remaining free GiB and the configured/default reserve **plus** expected next checkpoint space. On a normal protected storage stop, `DISK_RESERVE_REACHED` appears in the event ledger and operator output with exact budget details. The 100 GiB reserve and protected student or champion checkpoints remain intact; ADR-018 governs retirement of unreferenced run-local bundles. This matters for fast MLX sessions with many full model-and-AdamW bundles; resume remains human-owned once sufficient space is independently available.

**Updated checkpoint policy (ADR-018):** The human operator now authorizes best-score capability champions, even when below 100% of their rubric. A single full student+AdamW bundle may lead several capabilities; unreferenced former winners are retired after the newer state is durable. Ordinary lesson visits remain in memory and are not permanently archived. At each scheduled sealed examination or operator stop, the learner retains a complete recovery checkpoint; if testing reveals a new capability best, that same whole checkpoint is also a champion. Crash recovery returns to the last persisted assessment/stop boundary, potentially losing an unfinished group of visits, rather than claiming that an uncheckpointed update was durable. Grade promotion still requires 100% on one intact complete rubric. This is neither model soup nor held-out teacher reward. Original parent and sealed examination inventory remain unchanged.

**Grade A admission changed by explicit user decision:** the existing six foundational typed predicates and exact 144 teaching/72 examination examples are accepted as the experimental first tranche. This is not a declaration of full New Ithkuil surface-form legality. The live trainer loads the historical whole 222-token FP32 student and AdamW; **inherits the original adaptive teacher's 4,288 observations and 390 policy strategies**; uses only pinned teaching rows to train and reward teacher policies; examines the separate fixed 72-item rubric only at scheduled grade boundaries; and retains a complete model+optimizer+semantic-catalog bundle at each scored assessment or operator-stop boundary (ADR-018). Candidate Grade A mastery remains a same-checkpoint 72/72 standard and ends at `AWAITING_NEXT_GRADE` until a new grade is independently admitted. The trainer never rewrites the original checkpoint. See [Grade A source/MLX proof](docs/GRADE_A_REPAIR_AND_BACKEND_20261015.md) and [the trainer operating contract](docs/GRADE_A_HUMAN_TRAINER_20261015.md).

Inspect the candidate six-capability Grade A without a training run:

```sh
npm run curriculum:audit -- \
  --legacy-code-root ../bilqis-triplets-v16 \
  --champion-checkpoint ../bilqis-triplets-v16/runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt
```

The source probe requires three separately implemented interpreters to agree, including a new independent Grade A source-record oracle. It checks teaching/examination tokens, three- and four-entity world sizes, and the frozen vocabulary prefix. `docs/GRADE_A_SOURCE_PROBE_V1.json` preserves historical research; the **current** accepted source inventory remains `docs/GRADE_A_CANDIDATE_MANIFEST_V2.json` without rewriting its former candidate-state field. The separate `grade_a_release.py` version records the user's explicit acceptance. Source records remain typed-pasigraphy teaching material, not a claim of acquired NI mastery.

Reproduce the full candidate exam and nontraining Apple GPU parity independently:

```sh
npm run grade-a:verify
npm run mlx:qualify
npm run grade-a:baseline
npm run train -- --dry-run --verify-source
```

`grade-a:baseline` examines the unchanged historical student on all 72 fixed exam items (full five-state versus binary-constrained answer reports). `--verify-source` validates the 216 original source records in a neural-inert dry-run. The operator status now declares Grade A accepted and the human experimental trainer available; the broader NI grammar and first actual long-session outcome remain experimental uncertainty, not gates silently imposed over the user's decision.

## Data and storage boundaries

Source code lives here; ignored `runs/` and `artifacts/` never enter Git. The source pre-repair complete FP32 checkpoint is `student-116760-7e9af4651f28.pt` (SHA-256 `646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78`) from the original v16 run. It was audited at 1,052/1,150 **on the former rubric**; this is not a new-grade mastery claim. **No checkpoint files are copied by repository setup.** Existing v16, v2-r1 and v17 research lineages remain at their original locations.

Run the backup script **yourself** once an external disk is mounted and you have chosen the old worktrees/runs to retire. The first command is plan-only; the second is an explicitly bounded verified **copy**, never a move or deletion:

```sh
./scripts/backup-retired.sh plan --source "$HOME/Code/bilqis-triplets-v16" --destination "/Volumes/YourBackupDisk"
./scripts/backup-retired.sh copy --source "$HOME/Code/bilqis-triplets-v16" --destination "/Volumes/YourBackupDisk" --confirm-copy --max-gib 400
```

These are examples; name each actual retired source tree separately. The script rejects the whole `~/Code` directory, requires destination on a different volume for copy, includes dotfiles/ignored models and symlink identity (manifest-encoded on USB formats without POSIX symlinks), verifies every destination file against SHA-256, and **never deletes originals**. After copying, run `npm run backup:verify -- --manifest <printed-manifest-path>`. If a source directory is a linked Git worktree, its `.git` pointer does **not** include the shared Git object database; create a separate Git bundle before retiring Git history. The script uses exclusive file creation, not hard-link operations that fail on exFAT. Interrupted/partially copied files fail verification; nothing is deleted. Never treat a successful copy as an authorization to delete source data. Do not run broad filesystem cleanups, `git clean`, or recursive delete commands against `~/Code`.

## Verification

```sh
npm run test
npm run train -- --dry-run
```

MLX tests prove tiny-fixture restarts and optimizer agreement. The [actual-student disposable parity probe](docs/GRADE_A_REPAIR_AND_BACKEND_20261015.md) independently checks the full 39-parameter FP32+AdamW model against PyTorch. The experimental human trainer has also passed a complete **six-visit synthetic school run and rubric evaluation**, plus a **real-source, no-neural-update initialization/save/reload** check of the original whole student. This does not yet establish long-session convergence or a successful real-human Grade A training outcome.

See `AGENTS.md` and `docs/REQUIREMENTS.md` for implementation constraints and current gaps.

## Curriculum and New Ithkuil

The successor does **not** rename the old model's learned token identities. They remain frozen as the historic semantic ABI. New lessons and semantic roots will be source-attested separately, with graded prerequisites and independent oracles. The [curriculum registry reconciliation](docs/REGISTRY_RECONCILIATION_20261015.md) explains how the workbook's older provisional A/B/C tranche labels differ from the later controlling letter-grade plan. New Ithkuil alignments begin with [the official 2023 grammar's morphology](https://www.ithkuil.net/newithkuil_03_morphology.htm) and [numbers](https://www.ithkuil.net/newithkuil_13_numbers.htm); the research bridge mappings in `bilqis_mlx/ithkuil_alignment.py` are explicitly **not** yet executable teaching material.

### AST-driven curriculum planning

Rather than writing each lesson/probe by hand, the new `registry_ast.py` compiles a reproducible, **read-only native-Sheet snapshot** into typed semantic tokens, historical/proposed lessons, explicit same-grade prerequisite edges, grade plans, and New Ithkuil bridge research nodes. It retains extra qualification notes (such as Mood/presupposition constraints) without treating them as automatically runnable grammar. The admitted Grade A course binds separately to the exact 222-token ledger, with no semantic relabeling. Use:

```sh
npm run curriculum:plan
# Hypothetical proposed Grade C planning once A/B prerequisites are satisfied:
npm run curriculum:plan -- --grade C --assume-mastered A B
```

The default report enumerates five proposed Grade C construction tasks and their unmet dependencies. With the explicitly hypothetical A/B assumption, only its first task becomes *ready for curriculum authoring*, never ready for neural training. The command makes no model, optimizer, run-state, Sheet, or sealed-exam changes. The checked-in [Registry snapshot](docs/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json) was read from the native connected Google Sheet; it is pinned evidence, **not an automatically refreshing Sheet connection**. Refresh requires another native connector read and checked snapshot update. The compiler's executable source-probe family generates 96 source-oracled *candidate* Grade A worlds, none admitted as teaching/examination rows. See the [compiler design and remaining tasks](docs/CURRICULUM_AST_COMPILER_20261015.md).

### Vocabulary can expand

The preserved model's 222 tokens are a historical snapshot: 113 foundational symbols followed by 109 mathematics additions. There is no 222-token limit. The original implementation already supported append-only embedding/AdamW expansion; the MLX successor now has a separately tested, neural-inert growth adapter. Existing model answers remained exactly unchanged in an in-memory test of the real historical student with one added disposable token. The 330 entries in the connected Semantic Bridges worksheet are *research candidates*, not current neural tokens or mastered meanings. New Ithkuil morphology, external mathematical concepts and irreducibly lexicalized concepts can all be admitted later as appropriately sourced semantic identities. See [vocabulary architecture and proof](docs/SEMANTIC_VOCABULARY_GROWTH_20261015.md).

Run the same safe proof without changing or training the original model:

```sh
npm run vocabulary:preflight -- \
  --legacy-code-root ../bilqis-triplets-v16 \
  --checkpoint ../bilqis-triplets-v16/runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt
```

The source-attested Grade A and the scoped typed-formal Grade B connectives are executable under human-operated training. **Actual Grade A mastery is observed; Grade B acquisition, later New Ithkuil morphology, long-horizon multi-grade retention and Grade C admission are not yet proven.** Never use the agent-side harness to invoke `--human-run`.
