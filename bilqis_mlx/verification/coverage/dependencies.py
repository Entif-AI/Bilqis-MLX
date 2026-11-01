"""Impact closure over the discovered typed dependency graph."""
from ...errors import ErrorBus, SEMANTIC_COVERAGE
from .contracts import SCHEMA

def affected_typed_dependency_closure(plan: dict, changed: tuple[str, ...]) -> tuple[str, ...]:
    """Regenerate descendants of newly *discovered* as well as declared edges."""
    if plan.get("schema") != SCHEMA:
        ErrorBus.Raise(
            SEMANTIC_COVERAGE.PLAN.VERSION_MISMATCH,
            actual_schema=plan.get("schema"),
            expected_schema=SCHEMA,
        )
    reverse: dict[str, set[str]] = {}
    for edge in plan["obligations"]:
        reverse.setdefault(edge["producer"], set()).add(edge["consumer"])
        reverse.setdefault(edge["consumer"], set())
    known = set(reverse) | set(plan.get("capabilities", ()))
    if set(changed) - known:
        raise ValueError("SEMANTIC_COVERAGE_UNKNOWN_CHANGED_CAPABILITY")
    impacted = set(changed)
    pending = list(changed)
    while pending:
        for dependent in reverse.get(pending.pop(), ()):
            if dependent not in impacted:
                impacted.add(dependent)
                pending.append(dependent)
    return tuple(sorted(impacted))
