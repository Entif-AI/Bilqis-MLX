# B03.3 frame encoder ownership

Consumed unified and Lane B: `9104ce733e04fb9c82420428b18dfdbf5db49535`.
Issue: #444. Authority: IPR-0220 (OPEN). Existing incident control:
PM-2026-10-30-002, RC-112/PAT-035: preserve physical teacher-policy source paths.

The encountered 473-line `learning/frame_encoder.py` and 373-line nested test
require a local structural interruption. The saved `913db94` frame-only extraction
is reused because its original encoder and nested test are byte-identical to this
unified baseline. Its unrelated learning-package moves are omitted: unified already
has different accepted compartments. The original branch remains intact.

The public `learning.frame_encoder` package keeps existing input/output schemas,
record pickle identities, validation, tensor borrowing and arithmetic. Its owners
are contracts, compiled-prefix validation, vector records, numerical kernel,
source-bound member gathering, compiled execution and dispatch. Each is below
240 lines. Nested fixtures, gradients and visibility tests mirror those boundaries;
the old nested test path remains a fixture-import facade. Existing source-atom
regression callers continue importing the unchanged test-frame helpers.

Baseline CPU proof: 22 tests passed, zero skipped. The same equations, nested
gradients, prefix isolation and A05 source-atom regressions pass after extraction.
A dedicated pickle test checks every public frame record's historical module path.
No teacher-policy files, source compiler, canonical manifest or live run is changed.

The local Work Stack interruption precedes the separate exact lineage/count
acceptance assertions, fresh independent EGM and issue turn-in.
