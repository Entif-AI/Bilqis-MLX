"""Coverage schema, stable hashes and bounded historical audit policy."""
import hashlib
import json
from ...errors import ErrorBus, SEMANTIC_COVERAGE
from ...semantic_sampling import LEGACY_AUDIT_POLICY, audit_budget_violations

SCHEMA = "bilqis.mlx.semantic-composition-coverage/v1"

def require_coverage_audit_budget(max_rounds: object, each: object) -> None:
    violations = audit_budget_violations(max_rounds, each)
    if violations:
        ErrorBus.Raise(
            SEMANTIC_COVERAGE.AUDIT.INVALID_BUDGET,
            max_rounds=max_rounds,
            each=each,
            violations=violations,
            policy=(
                f"rounds={LEGACY_AUDIT_POLICY.minimum_rounds}.."
                f"{LEGACY_AUDIT_POLICY.max_rounds}; "
                f"minimum-per-outcome="
                f"{LEGACY_AUDIT_POLICY.sample_policy.minimum_per_outcome}; "
                "violations=" + ",".join(
                    f"{item.field}:{item.rule.value}" for item in violations)
            ),
        )


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()
