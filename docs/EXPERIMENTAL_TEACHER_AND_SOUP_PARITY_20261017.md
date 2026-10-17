# Bilqis: experimental teacher/retention and typed soup path (model-size parity)

**Status:** Implemented opt-in research branch, **not** an approved policy or
human learning outcome. The original human trainer and its saved school run are
unchanged. No actual student optimizer steps have been run by an agent.

**Source:** `~/.codex/worktrees/ff64/bilqis-mlx`,
`af2ae28e8ca1cae1152e68bb25823ce257d0b9fd`
(`codex/336-evergreen-factory`).

**Worktree:** `~/Code/.chat-on-steroids-worktrees/bilqis-teacher-soup-parity-20261017/bilqis-mlx`,
branch `codex/teacher-soup-parity-20261017`.

**Private specifications:** `socr8s/private-ip` issues
[#339](https://github.com/socr8s/private-ip/issues/339) (teacher and candidate
transaction), [#340](https://github.com/socr8s/private-ip/issues/340)
(soups, discordance and scalable screening), governing protected #336;
reused incident `PM-2026-10-16-010`. These protected links must be
screened if this code is projected to a public repository.

## What the alternative actually changes

The legacy default path is untouched when the experimental CLI flag is absent.
With `--experimental-retention`:

1. A **separate in-memory student and own AdamW** is forked from the parent
   before each bounded visit. The trial has 6 transformer layers, 384 hidden
   dimensions and 24 heads, exactly matching the incumbent geometry. Failed
   trials never enter the parent parameter or optimizer dictionaries.
2. A small, **bounded**, rotating, grade-stratified sentinel cohort is built
   only from admitted/current source-oracled capabilities. Parent and
   challenger predict the **same rows**. The current trial screens at most
   eight older/other capabilities plus the taught capability, six rows each
   (all values operator configurable). Known struggling skills receive
   priority; rotation examines apparently safe ones. The independent whole-
   school exam still measures every capability on the normal schedule.
3. A source-scored per-capability change vector detects the worst decline.
   **During `MAIN` introduction**, the provisional allowed per-capability
   loss is `mature_max_loss + introduction_extra_loss`; recovery uses
   `mature_max_loss`. Initial values 2+2 and 2 wrong answers respectively,
   measured on the tiny six-row sentinel, are **research knobs**, not
   ratified optimal thresholds. A failed trial is discarded. A passing trial
   is **provisionally retained**, not awarded any grade or champion standing.
4. The inherited teacher still selects its strategies and retains all old
   UCB statistics and event history. A separate, versioned contextual channel
   records paired beneficial or destructive action outcomes keyed by
   capability, phase and numeric curriculum scope. It penalizes observed
   protected losses and source-backed rejections; known-bad functional
   delta patterns become bounded (24) **negative archetypes**. Similarity
   against those patterns is advisory, not an unqualified hard rejection.
   For rejected trials the inherited reward is zero, not an invented success;
   causal outcome credit is stored in the new channel. Next policy picks can
   prefer supported better-context strategies while preserving base
   exploration and mutation. No retrospective multi-action attribution.
5. On **typed Grade C** lessons, the teacher's selected `old` allocation
   now draws actual older-grade, source-oracled rows where available, rather
   than inertly recording that knob. `contrast` changes source-group
   selection. `depth` can favor longer source-attested token sequences as
   an explicitly labeled **token-length proxy**, not proven AST depth.
   `preview` is marked unavailable rather than introducing unadmitted
   semantics. Actual delivered prior-grade counts are recorded *after*
   missed-example replay.
6. The frozen grade soups and same-grade perfect champions can now advise
   **typed numeric/evidence/native-token gradients** using bounded,
   gold-agreeing multi-class soft targets through the actual typed loss.
   Historical 222-token frozen mentors cannot vote in a 227-token native
   head they cannot represent. Existing binary advisory and the student's
   independent inference remain unchanged. Neither soups nor negative
   archetypes become student weights or examination authorities.
7. Full champion-frontier comparisons remain at scored checkpoint
   boundaries. The **per-visit safety** path never loads every champion.
   Thus expensive history comparison is separated from trial admission,
   without breaking protected perfect-capability custody.

## Explicit limits of the experiment

- Short source-oracled sentinels can miss regressions, including catastrophic
  losses on unsampled capabilities. Every decision records its sampled scope
  and the unsampled count. Normal cumulative exams, old champions and frozen
  grade soups remain protected. A provisional pass is **not graduation**.
- Functional negative archetypes are not a learned neural 'bad weight soup';
  signed dot-product/gradient projection is deliberately not yet operative.
  The archived data can support that subsequent disposable research.
- The contextual reward is a provisional local-gain-versus-retention-loss
  heuristic. Neither the threshold nor its discrimination/learning benefit
  has been calibrated on the human student's sustained trajectory.
- Two paired forward passes, some source generation, and a complete in-RAM
  candidate/AdamW clone add overhead. The sentinel inference component stays
  bounded as more capabilities are admitted, but **99% total runtime savings
  or 99% of gains preserved have not been measured**.
- Typed cross-grade rehearsal is currently a teacher-owned earlier-grade
  source-example selection, not a general AST prerequisite-learning factory.
  Token-length is an imperfect depth proxy and source future-grade previews
  remain prohibited.
- Scores from full human-run examinations are **not** back-propagated as
  arbitrary single-policy rewards after multiple interventions. The teacher
  learns from uniquely attributable, same-parent paired trial results.
- No new student architecture, vocabulary, oracle, static curriculum
  benchmark, graduation rule, archive retirement or human training
  authorization is introduced.

## Human-only parity experiment, after the current run finishes

First read the **plan**, which does not write:

```sh
cd ~/Code/.chat-on-steroids-worktrees/bilqis-teacher-soup-parity-20261017/bilqis-mlx
python3 -B scripts/prepare_learning_experiment.py \
  --source ~/Code/bilqis-mlx/runs/school-mlx-v1
```

After the original human training process stops and its checkpoint is durable,
the operator can choose to clone the full run into this separate worktree:

```sh
python3 -B scripts/prepare_learning_experiment.py \
  --source ~/Code/bilqis-mlx/runs/school-mlx-v1 --confirm-clone
```

This copies and SHA-verifies every saved run file, refuses symlinks, existing
targets and active trainers, retains the original, and requires a 100 GiB free
disk reserve plus copying headroom. It never archives/deletes the original.
The target is `runs/teacher-soup-parity-experiment`. To construct a matched
baseline/control branch, a second explicitly named `--destination` within
the same isolated `runs/` parent can be used.

With the cloned run, preview the proposed human-only training invocation:

```sh
npm run train -- --dry-run --resume --experimental-retention \
  --run-dir ./runs/teacher-soup-parity-experiment \
  --legacy-code-root ~/Code/bilqis-triplets-v16
```

Only the **human operator**, after separately reviewing the plan, may add
`--human-run --max-visits 12 --minutes 10` in an actual command. The program's
original own-AdamW, semantic source, disk headroom, exclusive operator lock,
grade staircase and full-exam requirements still apply. Compare against a
control clone of the same original source step, and inspect complete A/B/C
retention, attempted versus retained steps, teacher contextual rewards,
typed soup guidance events, wall-clock time and source-cohort coverage.

## Local software checks (no actual Bilqis training)

```sh
python3 -B -m unittest tests.test_learning_experiment \
  tests.test_causal_teacher_integration tests.test_typed_soup_experiment \
  tests.test_prepare_learning_experiment tests.test_experiment_parity_geometry
python3 -B -m unittest discover -s tests -q
```

The disposable fixture/test suite expects the pinned v16 source at an
adjacent `bilqis-triplets-v16` path. For this isolated worktree that
path is a symlink to the original read-only source in `~/Code`, installed
outside Git. The preflight still verifies original source fingerprints.
