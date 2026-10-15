# Bilqis MLX: private, independent successor

**State: implementation and validation in progress. No neural training is enabled.**

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
npm run train -- --dry-run
npm run train
```

`status`, `dashboard` and `--dry-run` are neural-inert. **`train` currently refuses to start.** Training will only be enabled after full migration, a source-grounded course, rubric, and explicit human launch. Do not use `--resume` to mean "start from the original old grade G12". Resumption applies only to a previously initialized *new* run.

Inspect the candidate six-capability Grade A without a training run:

```sh
npm run curriculum:audit -- \
  --legacy-code-root ../bilqis-triplets-v16 \
  --champion-checkpoint ../bilqis-triplets-v16/runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt
```

The audit checks two independent symbolic oracles, all teaching/examination source tokens, both three- and four-entity world sizes, and the saved student's frozen vocabulary prefix. Its machine-readable result is in `docs/GRADE_A_SOURCE_PROBE_V1.json`. The course remains a **proposal**, with no authorized neural lessons or new-grade mastery claim. The old source directory must be available for this transitional audit.

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

The MLX tests also prove disposable FP32 model+AdamW save/reload and four matching PyTorch/MLX optimizer updates starting at synthetic step 116760. They test gradient and clipping parity on a tiny fixture. See [the fixture receipt](docs/MLX_DISPOSABLE_ADAMW_RESTART_20261015.md). The complete trained student's optimizer still requires separate continuation qualification.

See `AGENTS.md` and `docs/REQUIREMENTS.md` for implementation constraints and current gaps.

## Curriculum and New Ithkuil

The successor does **not** rename the old model's learned token identities. They remain frozen as the historic semantic ABI. New lessons and semantic roots will be source-attested separately, with graded prerequisites and independent oracles. The [curriculum registry reconciliation](docs/REGISTRY_RECONCILIATION_20261015.md) explains how the workbook's older provisional A/B/C tranche labels differ from the later controlling letter-grade plan. New Ithkuil alignments begin with [the official 2023 grammar's morphology](https://www.ithkuil.net/newithkuil_03_morphology.htm) and [numbers](https://www.ithkuil.net/newithkuil_13_numbers.htm); the research bridge mappings in `bilqis_mlx/ithkuil_alignment.py` are explicitly **not** yet executable teaching material.

### Vocabulary can expand

The preserved model's 222 tokens are a historical snapshot: 113 foundational symbols followed by 109 mathematics additions. There is no 222-token limit. The original implementation already supported append-only embedding/AdamW expansion; the MLX successor now has a separately tested, neural-inert growth adapter. Existing model answers remained exactly unchanged in an in-memory test of the real historical student with one added disposable token. The 330 entries in the connected Semantic Bridges worksheet are *research candidates*, not current neural tokens or mastered meanings. New Ithkuil morphology, external mathematical concepts and irreducibly lexicalized concepts can all be admitted later as appropriately sourced semantic identities. See [vocabulary architecture and proof](docs/SEMANTIC_VOCABULARY_GROWTH_20261015.md).

Run the same safe proof without changing or training the original model:

```sh
npm run vocabulary:preflight -- \
  --legacy-code-root ../bilqis-triplets-v16 \
  --checkpoint ../bilqis-triplets-v16/runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt
```

Current training is still blocked because no newly versioned Grade A rubric and completely verified MLX optimizer continuation exist. Safe inspections run through the same npm interface and can be run by agents without requesting operator time.
