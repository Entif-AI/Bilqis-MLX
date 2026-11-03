# C10 structural follow-up #641: current integration and historical preservation

3 November 2026 UTC; Lane C #344. IPR-0220 governs. This candidate consumes
reviewed unified `dfc0c7586c23b6477c08d4db486ade3deeb79fae` from Lane C
`af5e3ce4`. Historical candidate `aa2aec1809256a6270bb8afedc87c2a655175054`
has been consumed without reverting subsequent reviewed B05 changes.

## Current acceptance

The original extraction already landed via #652. This candidate adds only the
public `depth_parameter_view.__module__` identity repair and its pickle regression
to current production/test sources. `verify_current_integration.py` compares every
current direct depth production/test file against the immutable consumed unified
commit. It permits exactly that metadata line and literal regression; any other
source change, missing/additional file or structural-target failure rejects.
`current-integration.json` additionally binds all inspected bytes and both new
verification helpers. These checks preserve the accepted source-selection,
generation identity and source-authority changes in unified.

The old `verify_preservation.py --check` remains unchanged. Its evidence applies
only to the historical candidate: running it against current sources correctly
fails with `definition/decorator drift: DepthParameterView`. Historical AST
identity must not be claimed for the changed current B05 implementation. No quality
baseline, original definition digest, assertion or threshold was weakened.

Executed proof: historical `PRESERVATION_RECEIPT_OK`; current depth CPU suite
**15 passed, zero skips**; historical/current verifier adversaries **9 passed**;
current exact-overlay receipt passes. Historical production/test inventories retain
15/27 original definitions. Current owners remain below 240 lines with at most
12 direct Python files. Historical counts below describe their pinned snapshot.

## Fresh-environment reproduction

Prerequisites: macOS 14+ Apple Silicon, Python 3.14 with venv/pip, Git history
containing both pinned commits, network access for the declared packages, and this
candidate checked out at repository root. These tiny CPU checks do not initialize
or train a persistent student. No source fixture or saved run is required.

```sh
C641_REPO="$PWD"
C641_GIT_DIR=$(git rev-parse --path-format=absolute --git-common-dir)
C641_WORK=$(mktemp -d "${TMPDIR:-/tmp}/bamf641-proof.XXXXXX")
python3 -m venv "$C641_WORK/runtime"
C641_PY="$C641_WORK/runtime/bin/python"
"$C641_PY" -m pip install mlx==0.32.4 numpy==2.5.4 cryptography==50.0.2 \
  -r "$C641_REPO/lib/ithkuil/requirements-semantic.txt"
"$C641_PY" -B -m unittest discover -s docs/evidence/bamf/C10.2-641 -p 'test_*.py' -v
"$C641_PY" -B docs/evidence/bamf/C10.2-641/verify_current_integration.py --check
"$C641_PY" -B - <<'PYCPU'
import mlx.core as mx, runpy, sys
mx.set_default_device(mx.cpu)
sys.argv = ['scripts/run_tests.py', 'bilqis_mlx/runtime/tests/depth']
runpy.run_path(sys.argv[0], run_name='__main__')
PYCPU
mkdir "$C641_WORK/historical"
git archive aa2aec1809256a6270bb8afedc87c2a655175054 | tar -x -C "$C641_WORK/historical"
(
  cd "$C641_WORK/historical"
  GIT_DIR="$C641_GIT_DIR" PYTHONPATH=. "$C641_PY" -B - <<'PYHISTORY'
import mlx.core as mx, runpy, sys
mx.set_default_device(mx.cpu)
sys.argv = ['verify_preservation.py', '--check']
runpy.run_path('docs/evidence/bamf/C10.2-641/verify_preservation.py', run_name='__main__')
PYHISTORY
)
```

The fresh runtime used MLX 0.32.4, NumPy 2.5.4 and cryptography 50.0.2.
The historical archive is read using the repository's Git object database;
no branch is switched or rewritten. The original preservation JSON is retained
byte-for-byte. New overlay checks pin accepted successor sources independently.
Current EGM/hosted status belongs to the exact issue/PR receipts, not historical
PR #739. No acceptance of B11 producer authority, B08 admission, retained learning,
#355 or #586 follows from this structural turn-in. No self-merge or durable student,
own AdamW, teacher, champion, source release or graph mutation is authorized.

## Historical receipt — aa2aec18 only

The following record describes the previous snapshot and its original failures.
Its old reproduction commands must run inside that snapshot, as shown above.


2026-11-02; Lane C #344; issue #641; structural parent #520. IPR-0220 governs.
Base: synchronized Lane C `46bfa98d564e1262be43463ec96d3ce1a95aa8c4`, containing
reviewed unified `67c964a1548cb0075a28a90aa2565d8bdab0fd71`.
The historical #639 dependency was superseded by accepted #655, merged as
`aedeff542d61f0bfd46dc517d44b85ef187aaec9`; #637 is closed completed.

## Existing implementation

The prescribed structural work already landed in PR #652 (merged 2026-10-31),
commit `cec6a8ee1659854c292dc59566d4d14a53b75ae5`. This proof-only change reuses it.
The old 365-line `runtime/block_attnres.py` is now the 205-line numerical/API owner
`runtime/_depth/block_attnres.py` plus 197-line `depth_contracts.py`. The latter owns
parameter views and their shared private seal, feature/summary records, schema
constants and B01 prefix validation. The numerical owner retains feature composition,
normalized depth selection, gates, diagnostics and group-boundary execution order.
There is one public module identity, `bilqis_mlx.runtime.block_attnres`.

The 491-line original test owner is mirrored into contracts (161 lines), numerical
proof (194), public integration (119) and shared helpers (125). Production has
three direct Python files including package initialization; tests have five. Every
file is below 240 lines and each directory has at most 12 direct code files.

## Reproduce preservation and behavior

From repository root with the normal MLX dependencies installed:

```sh
python3 -B -m unittest discover -s docs/evidence/bamf/C10.2-641 -p 'test_*.py' -v
PYTHONPATH=. python3 -B docs/evidence/bamf/C10.2-641/verify_preservation.py --check
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/depth
```

The inventory tests run without MLX. The verifier reads the accepted pre-split
owner directly from Git and hashes location-independent ASTs. It requires all 15
original top-level production functions/classes and all 27 original test/helper
functions to remain exact. Only the test/helper inventory recurses into nested
functions; production definitions already include their nested bodies in each AST.
Decorators are included. Lexical names and hash occurrence counts preserve duplicates; two identical extra
`setUp` copies support the three split test classes. It rejects missing/changed
definitions and
checks file/directory targets and the canonical import/pickle global references
for every original class and public function, including DepthSelectionDiagnostics.
It reads historical protocol0 references and checks new protocol0 bytes, plus
canonical physical import owners and relocated aliases. It does not pickle
student instances or sealed tensor views. `--check` compares regenerated evidence
with committed `preservation.json` and fails on any difference. Each inspected
production/test/verifier file is SHA256-bound; source edits invalidate the receipt. The helper is read-only; it neither
initializes a student nor updates an optimizer.

The behavioral suite passed **14/14 on CPU**, zero skips. Tests retain independent
selector equations, normalization/gates and gradients, type-mean/UNKNOWN and
source-coordinate behavior, public parameter/source/schema rejection, exact
B01 views and group/motif/capture/adapter order. All original function/class ASTs and test decorators remain exact. #740 adds
one public factory pickle-identity regression and restores only that function
module metadata; no equation, validation, seal or baseline is changed.
The existing B05.4 fail-closed admission disposition remains intact.

## Scope and remaining owners

This submits the existing extraction for structural #641 acceptance. #355 and
#586 remain open; #520 is already closed completed under its own acceptance. It grants no
trusted B11 summary-producer authority, source admission, B08 hit, checkpoint or
retained learning. No actual student, own AdamW, teacher, champion or human-run
was changed. No fresh semantic rule or neural experiment was introduced.

This checked-in record is a local source-proof checkpoint, not live CI state.
The lane head_sha pins the tested implementation checkpoint; a file cannot contain
its own final commit SHA. Native PR #739 metadata and issue comments bind each
subsequent candidate SHA to hosted checks and final pinned EGM. Read those native
receipts for current CI/review state. Existing related incidents
PM-2026-11-02-003 (committed-scope proof) and PM-2026-11-02-007 (live public visibility)
remain applicable; public receipts use opaque IPR-0220.

## Corrected evidence failure

PM-2026-11-02-008 records the failed bare-name verifier at `068eb6bf`, its empty
JSON and premature 24-definition claim. Those artifacts are superseded by this
lexically scoped, multiplicity-preserving receipt. Five adversarial tests cover
nested-name collisions, removed duplicates, decorator loss, repeated setup and stale committed JSON.
Dependent commands now use successful exit status before generating or publishing
evidence. No runtime source changed during the correction.

## #740 identity and receipt repair

Pinned EGM at46ab5891 found missing direct import/pickle and committed-JSON
comparison proof. The new identity regression exposed that the accepted extraction
wrote depth_parameter_view pickles under runtime.depth_contracts. Its old public
reference still read successfully. Restoring __module__ preserves the historical
public pickle bytes without altering function AST/body or sealed-state behavior.
PM-2026-11-02-009 records the failing-before mismatch; PM-008 remains the separate
failed-generation incident. Verifier5/5, source identities, exact JSON comparison
and CPU depth14/14 are the repaired proof surfaces; final whole-candidate EGM
remains recorded on PR739 rather than inferred from these tests.
