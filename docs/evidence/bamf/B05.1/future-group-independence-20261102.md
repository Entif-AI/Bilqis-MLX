# B05 future-group independence witness — #756

Consumed reviewed unified `2800946729e484875f7d1f57f0e6d85078936394`.
Scoped repair source: `25c626c39ef865d82a14498d23b38a82bb1af03b`, branch
`codex/756-future-group-witness`. No production selector code changed.

The original test computed `unrelated_future` but never supplied it to a competing
execution. It compared two identical earlier calls. That block is removed; the
independent numerical oracle, boundary order, illegal future-source admission,
gate, gradient and normalization checks remain.

The replacement executes all three numerical boundaries twice over two complete
source-state collections. The collections differ only in g2, then only in g3.
At each boundary the numerical selector receives its completed source prefix.
Every output before the changed group's completion must remain byte-equal. The
output at the changed group's own boundary must differ, establishing that the
changed tensor actually participates in the competing execution.

The mutation control deliberately contaminates an earlier boundary's current
state with the not-yet-completed group's hidden tensor. The same paired-execution
assertion then fails. This is explicit test-runner fault injection, not an added
production path or a claim that numerical tests qualify backbone provenance.
The permanent negative test requires this assertion failure for both g2 and g3.

## Verification

Native Apple Silicon/MLX 0.32.4, NumPy 2.5.4. Expected failing mutation probe:

```sh
python -B - <<'PY'
from bilqis_mlx.runtime.tests.depth.test_future_group_independence import FutureGroupIndependenceTests
case = FutureGroupIndependenceTests()
case.setUp()
case._assert_future_independence(
    lambda sources: case._boundary_outputs(sources, future_read=2), 2)
PY
```

Observed exit 1, `AssertionError: Arrays are not equal`, maximum absolute
difference `100.00116`. The correct paired executions and permanent mutation
negative both pass. The package-free repository runner initially exposed a
relative test import; the final test uses its canonical absolute import.

```sh
python -B scripts/run_tests.py bilqis_mlx/runtime/tests/depth
```

Final result: `TEST_TOTALS total=15 passed=15 failed=0 skipped=0 errors=0`.
Both changed Python files pass structure and hygiene checks with zero findings;
whitespace is clean.

This resolves #756's bounded numerical proof defect. Parent #449 retains its
whole-leaf producer and integration obligations. #577/#586/#757 independently
govern production selector provenance; this proof does not close them. Under the
current EGM execution policy, the next fresh pinned EGM belongs to the complete
merge-ready parent after its known engineering queue is consumed. No child EGM,
new PR, self-merge or persistent student/optimizer/teacher/champion/checkpoint
mutation accompanies this repair.
