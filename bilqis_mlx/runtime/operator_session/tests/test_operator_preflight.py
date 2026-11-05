"""Operator preflight validation does not enter the human-only loop."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from unittest.mock import patch as patch_modules
from bilqis_mlx.runtime.operator_session import operator_preflight as subject


def validate_operator_preflight(**kwargs):
    names = ['paths', 'experiment_runs', 'admission', 'state_dag']
    replacements = {name: kwargs.pop(name) for name in names}
    with patch_modules.multiple(subject, **replacements):
        return subject.validate_operator_preflight(**kwargs)



def options(**changes):
    values = dict(
        run_dir="unused", minutes=90, steps_per_visit=16, max_visits=0,
        batch_size=32, source_prefetch_workers=2, stagnation_grace_grade=None,
        stagnation_grace_steps=0, resume=False, flash_mode=False,
        boolean_composite=False, boolean_idboolops=False,
        boolean_association_bridge=False, admit_next_grade_with_debt=False,
        numeric_staircase=False, autonomous_curriculum=False,
        retention_enabled=False, experiment_budget=None,
        paths=SimpleNamespace(), experiment_runs=SimpleNamespace(),
        admission=SimpleNamespace(), state_dag=SimpleNamespace(),
    )
    return {**values, **changes}


class OperatorPreflightTest(TestCase):
    def test_rejects_invalid_limits_before_run_preflight(self):
        with self.assertRaisesRegex(ValueError, "^HUMAN_TRAINER_INVALID_OPERATOR_LIMITS$"):
            validate_operator_preflight(**options(minutes=True, retention_enabled=True))

    def test_grace_requires_explicit_resume(self):
        with self.assertRaisesRegex(ValueError, "^STAGNATION_GRACE_REQUIRES_EXPLICIT_RESUME_REQUEST$"):
            validate_operator_preflight(**options(stagnation_grace_grade="A", stagnation_grace_steps=1))

    def test_training_run_check_precedes_budget_allocation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            events = []
            budget = SimpleNamespace(assert_can_allocate=lambda amount: events.append(("allocate", amount)))
            runner = SimpleNamespace(require_training_run=lambda run, root, **kw: events.append(("run", run, root, kw)))
            validate_operator_preflight(**options(run_dir=root, retention_enabled=True,
                experiment_budget=budget, experiment_runs=runner, paths=SimpleNamespace(REPO_ROOT=root)))
            self.assertEqual(events, [("run", root, root / "runs", {"issue_budget": budget}),
                                      ("allocate", 600_000_000)])
