# Bilqis MLX: private, independent successor

**State: User-accepted six-capability Grade A; an experimental human-operated MLX trainer is available. Agents do not run actual student training.**

This private repository implements the successor directed by protected IPR-0220. Its public interoperability-facing summaries are Bilqis #160 (MLX backend qualification) and #162 (successor integration). The detailed internal curriculum, promotion and resource policy stays private.

**Founding premise:** Bilqis learns a deliberately defined shared pasigraphy, not an opaque tokenizer that we attempt to interpret afterward. Each token is a stable, individually interpretable semantic identity or function, registered one-to-one in the canonical curriculum spreadsheet. Composite meanings use **multiple known tokens** assembled according to faithfully implemented New Ithkuil lexicon, morphology and grammar rules. The training regimen itself is a progressively expanding conformance test suite for that language, intended to give different AI systems and human oversight specialists a common, inspectable lingua franca. This cataloging contract holds for every learned token until at least completion of the New Ithkuil course; future freedom beyond our dialect is a separately governed transition. See [foundational pasigraphy contract](docs/PASIGRAPHY_TOKEN_CONTRACT_20261015.md).

**Living catalog:** models pin their approved semantic ABI while spreadsheet descriptions and New Ithkuil correspondences evolve. Propose, review, approve and version changes; never discard learned weights due to an editorial update. Search the official Ithkuil grammar and lexicon before inventing roots. See [the living-ledger policy](docs/LIVING_PASIGRAPHY_LEDGER_20261015.md).

For the historical 222-token New Ithkuil crosswalk, the user delegated semantic-review decisions to the assistant (protected IPR-0220 comment `6187168824`). Any approved version must distinguish exact, qualified, compositional, native protocol and unresolved relationships; it does not certify an executable New Ithkuil wordform or neural learning.

The current native ledger successor `mapping-review/20261015-d` has 222/222 explicit reviewed semantic classifications and preserves the predecessor in `Token Mapping Reviews vC Snapshot`. Its 94 newly adjudicated tokens are individually documented in [the source-checked NI adjudication](docs/NI_SEMANTIC_ADJUDICATION_VD_20261015.md); no New Ithkuil surface wordforms or student language competence are certified. The prior model remains pinned to `legacy-source/v1`. Formal composition, grammar, and proficiency testing remain ahead, not silently passed.

The [first executable NI construction slice](docs/NI_CONSTRUCTION_SCOPE_20261015.md) handles 0..100 numerals with TNX, THM/PAR, optional shortcut morphology, and simple neutral monadic referentials. `python3 -m bilqis_mlx.ni_construction number 42` produces a source-linked analysis; `python3 -m bilqis_mlx.ni_construction parse-number ksalirsa` reverses it. `python3 -m bilqis_mlx.ni_construction_audit` emits 101 historical-token-indexed research rows. Only five numerical wordforms are literal Ch.13 witnesses; others are rule-derived and remain independently uncertified. This adds no learned tokens, lessons, or neural updates.

The prior 29 `G##` units are **capabilities**. This new school uses lettered **grades** (A, B, C...) with about six to nine prerequisite-compatible capabilities per grade. A run starts with grade A unless the operator explicitly supplies `--resume`. A grade is mastered only by one complete candidate model and its *own* optimizer scoring 100% on all that grade's tests at the same checkpoint. Past grade champions vote once *per represented grade*, even when multiple pointers share one physical checkpoint. Weighted whole-school soup makes a teacher only, never a synthetic trainable student.

Read [whole-student MLX parity evidence](docs/MLX_FULL_STUDENT_PARITY_20261015.md) and [Grade A source audit](docs/GRADE_A_SOURCE_AUDIT.md) before suggesting training.

Development rules: do not invent untaught roots, do not examine composed semantics before mastered constituents, and do not inherit the historic 1,150-question exam as the new graduation rule. Preserve the old entire FP32 checkpoint and its AdamW. MLX conversion is fail-closed until actual full-state parity is proven.

## Operator interface

Run from this repository:

```sh
npm run status
npm run dashboard
npm run train -- --dry-run --verify-source
npm run train -- --human-run --minutes 90
# Later, resume the same saved Grade A student:
npm run train -- --human-run --resume --minutes 90
```

`status`, `dashboard` and `--dry-run` are neural-inert. `npm run dashboard` now **replays the saved event ledger and displays the latest six-panel School50 snapshot even after training stops**. A human training command on an interactive terminal presents the same dashboard **in that terminal**, redrawing after each committed visit or sealed exam; when training stops it leaves a final read-only snapshot. Non-TTY runs retain JSON event output. **Actual student training requires the human to supply `--human-run`**. A run with existing saved content must use `--resume`; omitting it deliberately blocks a fresh start and prints the safe resume command. The default is 90 minutes, at most 48 complete capability visits and 16 optimizer steps per visit; all can be adjusted using `--minutes`, `--max-visits`, `--steps-per-visit` and `--batch-size`. A single visit must finish before the trainer advances the persistent state. Interruptions recover the last *committed* complete student plus its own AdamW, without reinterpreting `--resume` as the old G12 curriculum. Check `npm run status` to see current grade, phase, student SHA, optimizer step and teacher events.

**Grade A admission changed by explicit user decision:** the existing six foundational typed predicates and exact 144 teaching/72 examination examples are accepted as the experimental first tranche. This is not a declaration of full New Ithkuil surface-form legality. The live trainer loads the historical whole 222-token FP32 student and AdamW; **inherits the original adaptive teacher's 4,288 observations and 390 policy strategies**; uses only pinned teaching rows to train and reward teacher policies; examines the separate fixed 72-item rubric only at scheduled grade boundaries; and appends a complete model+optimizer+semantic-catalog bundle after each visit. Candidate Grade A mastery remains a same-checkpoint 72/72 standard and ends at `AWAITING_NEXT_GRADE` until a new grade is independently admitted. The trainer never rewrites the original checkpoint. See [Grade A source/MLX proof](docs/GRADE_A_REPAIR_AND_BACKEND_20261015.md) and [the trainer operating contract](docs/GRADE_A_HUMAN_TRAINER_20261015.md).

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

The accepted source-defined Grade A tranche can be run experimentally by its human operator without waiting for the full New Ithkuil grammar. Full New Ithkuil morphological conformance, Grade B curriculum, long-horizon retention and actual trained Grade A mastery remain future milestones. Never use the agent-side harness to invoke `--human-run`.
