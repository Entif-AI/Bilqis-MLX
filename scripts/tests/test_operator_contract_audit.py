"""New raw diagnostic identities and opaque numeric guards must not grow."""
import unittest

from scripts.operator_contract_audit import (
    analyze_source, debt_counter, new_debt,
)


class OperatorContractAuditTests(unittest.TestCase):
    def test_recover_exact_error_status_and_gate_code_without_guessing_semantics(self):
        source = '''
def work(debt, events):
    if not debt:
        raise ValueError("AN_EXACT_ERROR_CODE")
    debt.append("STAGED_SUCCESSOR_BINDING_REQUIRED")
    events.append({"event": "SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED",
                   "stop_reason": "AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED"})
    reason = ("AUTONOMY_JIT_PROPOSAL_READY" if debt else "AUTONOMY_SAFE_HOLD")
'''
        findings = analyze_source("bilqis_mlx/work.py", source)
        matches = {(item.code, item.kind) for item in findings.codes}
        self.assertIn(("AN_EXACT_ERROR_CODE", "exception"), matches)
        self.assertIn(("STAGED_SUCCESSOR_BINDING_REQUIRED", "gate"), matches)
        self.assertIn(("SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED", "event"), matches)
        self.assertIn(("AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED", "status"), matches)
        self.assertIn(("AUTONOMY_JIT_PROPOSAL_READY", "status"), matches)

    def test_opaque_policy_numbers_are_caught_but_named_constraints_are_not(self):
        bad = '''
def audit(each, max_rounds):
    if not 1 <= max_rounds <= 32 or each < 4 or each % 2:
        raise ValueError("BAD_AUDIT_BUDGET")
'''
        good = '''
def audit(each, max_rounds, policy):
    if not policy.accepts_rounds(max_rounds) or policy.sample_violations(each):
        ErrorBus.Raise(DomainErrors.BUDGET_INVALID)
'''
        bad_result = analyze_source("bilqis_mlx/a.py", bad)
        good_result = analyze_source("bilqis_mlx/a.py", good)
        self.assertEqual(
            {item.token for item in bad_result.debt
             if item.kind == "opaque-numeric-guard"},
            {"2", "4", "32"},
        )
        self.assertEqual(good_result.debt, ())

    def test_baseline_is_position_stable_and_fails_new_debt(self):
        before = analyze_source(
            "bilqis_mlx/a.py",
            'def run(v):\n if v > 32: raise ValueError("OLD_CODE")\n',
        )
        moved = analyze_source(
            "bilqis_mlx/a.py",
            '\n\ndef run(v):\n if v > 32: raise ValueError("OLD_CODE")\n',
        )
        added = analyze_source(
            "bilqis_mlx/a.py",
            'def run(v):\n'
            ' if v > 32: raise ValueError("OLD_CODE")\n'
            ' if v < 4: raise ValueError("NEW_CODE")\n',
        )
        self.assertEqual(new_debt(debt_counter(moved.debt),
                                  debt_counter(before.debt)), ())
        self.assertEqual({item[2] for item in new_debt(
            debt_counter(added.debt), debt_counter(before.debt))},
            {"NEW_CODE", "4"})

    def test_plain_english_raw_exception_literal_is_not_an_escape_hatch(self):
        source = '''
def crash():
    raise ValueError("invalid input")
'''
        findings = analyze_source("bilqis_mlx/another.py", source)
        self.assertIn(("literal-error-identity", "invalid input"),
                      {(item.kind, item.token) for item in findings.debt})


if __name__ == "__main__":
    unittest.main()
