# C637 B01 tensor-owner structural follow-up

Issue #637, parent structural owner #520, normative B01 owner #346. This is
structural conformance evidence, not a replacement algorithm specification.
The user's sustained Lane B instruction authorizes Lane C fallback when blocked.
B09.2 #465 encountered B01's714-line tensor owner and525-line test; its structure
gate also required the runtime/test roots to reach<=12 direct code files. Existing
Lane C #614 owns that grouping, so the B patch is preserved rather than importing
an unreviewed sibling lane into B.

## Exact branch and prerequisite

`codex/bamf02-c10-637-topology-20261030` is cut from current Lane C and consumes
reviewed unified `9104ce733e04fb9c82420428b18dfdbf5db49535`. It merges exact
same-lane prerequisite PR614 at `9ba8878be6790a27e23d0921c7369346ac6e9b21`.
The resulting pre-edit baseline is `f9290e3c130e4a8eea7fca5b799533a81469ef48`.
No main or sibling-lane merge occurs. PR614 and inherited Lane C work still need
human integration; this follow-up does not complete #520 or confer service,
rights, admission, retained-generation or learning acceptance.

B465's original local patch remains stashed at
`8b1a09cb082304e09cd405786fb05c48585d1033` and recorded in Work Stack
`15fb0c89-b0b0-40ed-99b6-fe4ef995aaf8`; it has no implementation/PR acceptance.
The C follow-up uses Work Stack `872e5c21-92e4-4461-bc87-dbcd96b42791`.

## Preserved ownership and behavior

The original tensor source is byte-identical on this C baseline. Its92-line
`runtime/model_topology_v2.py` facade imports cohesive `runtime/topology_v2/`
owners for frozen spec identity, dimensions, generation/parameter records,
normative ledger, initialization, source factors, validation, disposable
construction and stable serialization. All30 original production function/class
ASTs are preserved exactly. All public symbols and eight historical record/enum
module/pickle identities remain. Dependency imports are acyclic.

No tensor name/order/shape/group/category/decay/initializer, seed, norm, optimizer
value, storage key, source-factor equation or UNBOUND status changes. The actual
214-tensor census remains79,469,798 parameters, with the original literal category
subtotals and independent initializer/row/storage goldens. Source admission and
production writer custody remain with their existing owners.

C614 already moved tests into `runtime/tests/model/topology/`. This patch reuses
that package and mirrors the new source owners there. All21 inherited test
methods remain plus one literal historical-pickle regression. The historical
model-test facade and `ModelTopologyFixture` identity remain unchanged; the helper
adds an alias for the mirrored classes. All new source/test owners are<240 lines;
the original runtime/test roots retain12 direct code files each. There is no
recursive directory sweep or second root grouping.

Select `runtime/tests/model/topology/` for the complete topology proof. The old
`tests/model/test_model_topology_v2.py` was already a no-test fixture facade in
C614; this delta does not introduce that behavior. A reviewer initially flagged
the old B target collecting zero, then verified the actual C baseline and
retracted the regression finding. No duplicate compatibility test collection is
added and historical dated evidence is not rewritten.

## Test-decorator near miss

C614's grouped optional full-allocation and historical-v1 witness methods lacked
their original `unittest.skipUnless` decorators. Its exact unmodified compatibility
module reproduces3 passes/1 error without the historical bundle:
`KeyError: 'BILQIS_V1_BUNDLE_WITNESS'`. This is a literal inherited condition,
not an assertion that production tensors changed. The extraction mechanism is
not independently established.

The original pre-grouping conditions are restored, not broadened. The full
disposable witness is actually executed with `BILQIS_BAMF_FULL_WITNESS=1`;
the unavailable historical-v1 bundle remains an explicit skip. Canonical
PM-2026-10-30-006 was filed and read back, and PR614 received the finding/containment
receipt. Method body comparison also records the equivalent config-root
expression; no assertion or acceptance criterion is removed.

## Verification

The B-source baseline/extraction union each has45 total:43 pass/2 optional skips.
The actual C follow-up union with full disposable allocation has**46 total:
45 pass,0 failures/errors,1 unavailable historical-v1 witness skip**. This includes
the full tensors/native AdamW/safetensors round-trip and grown bank/page key and
byte preservation. No real student or original historical artifact is modified.

```sh
BILQIS_BAMF_FULL_WITNESS=1 \
node ~/.codex/hooks/validation-output-runner.mjs -- python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/model/topology \
  bilqis_mlx/runtime/tests/model/test_atlas_optimizer.py \
  bilqis_mlx/runtime/tests/model/test_atlas_plasticity.py
python3 -B scripts/check_module_size.py bilqis_mlx/runtime bilqis_mlx/runtime/tests
python3 -B scripts/quality/check_governance_integrity.py --base-ref f9290e3c
python3 -B scripts/code_smell_audit.py --changed-from f9290e3c \
  --check-baseline docs/evidence/development/code_smell_baseline.json
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
git diff --check f9290e3c...HEAD
```

Structure, architecture and docs pass on the candidate. The architecture pass
consumes C614's detector repair distinguishing actual adapter-factor
A/B suffixes from grade identity dispatch; this patch preserves ParameterSpec's
category AST. It does not change a guard, threshold or baseline. Independent
Goldfish at pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c` verified the
actual C-baseline AST/public symbols/pickles/import graph and focused tests;
no scoped Blocker/Major/minor remains. Committed-head quality and installed-wheel
readback are recorded with final issue/PR receipts.

IPR-0220 remains open. No actual student, own AdamW, teacher, champion, checkpoint,
source admission or human-run state changes. Human sign-off owns integration.
After this prerequisite arrives through reviewed unified, resume B465's saved
participation work and B466's separately blocked actual retained-promotion seam.

Installed-wheel witness: built `bilqis_mlx_private-0.5.0-py3-none-any.whl` with
SHA256 `e88c0745132bd59ebe3bec096e8d1506b135b53dfa5a38c7f06e56aea841ebcc`;
installed without dependencies into an isolated virtual environment, then ran
from a separate temporary working directory. The import resolved inside that
venv's actual site-packages. Its214-tensor/79,469,798 census, independent adapter
initializer golden, literal stable storage key, eight public type identities and
historical pickle GLOBAL all passed. This is package/import/tensor-contract proof,
not source corpus packaging, production admission or actual training.
