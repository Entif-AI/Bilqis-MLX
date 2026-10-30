"""Stable stagnation control API with cohesive implementation owners."""
from __future__ import annotations
from copy import deepcopy
from .contracts import (
    SCHEMA, GRACE_SCHEMA, RECOVERY_PHASES, NON_TERMINAL_STAGNATION_GRADES, MINIMUM_NO_PROGRESS_SECONDS,
    _validate_grace, _require_optimizer_step, _valid_checkpoint, _validate, _validate_required_capabilities,
    _validated_score,
)
from .grace import (
    create_optimizer_step_grace, reconcile_optimizer_step_grace, grace_suppressed_capabilities,
)
from .scope import (
    start_session, reconcile_required_scope, quarantined_capabilities, activate_sole_grade_rehabilitation,
)
from .progress import (
    record_visit, observe_paired_progress, begin_recovery_cycle,
)
from .recovery import (
    _rejected_without_retention, _warning_signals, _stagnation_evidence, complete_recovery_cycle, end_of_run_alerts,
)

for _export in (
    _validate_grace, _require_optimizer_step, create_optimizer_step_grace, reconcile_optimizer_step_grace, grace_suppressed_capabilities,
    _valid_checkpoint, start_session, _validate, _validate_required_capabilities, reconcile_required_scope,
    quarantined_capabilities, activate_sole_grade_rehabilitation, record_visit, _validated_score, observe_paired_progress,
    begin_recovery_cycle, _rejected_without_retention, _warning_signals, _stagnation_evidence, complete_recovery_cycle,
    end_of_run_alerts,
):
    _export.__module__ = __name__
del _export
