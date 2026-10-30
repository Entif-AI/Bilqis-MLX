from bilqis_mlx.learning.stagnation_control import (
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    quarantined_capabilities, record_visit, start_session,
    create_optimizer_step_grace, grace_suppressed_capabilities,
    observe_paired_progress, reconcile_optimizer_step_grace,
    reconcile_required_scope,
)

import unittest

def session():
    return start_session(session_id="human-command-1", generation=10,
                         required_capabilities=("B.AND", "B.NOT", "B.XOR", "B.OR", "C.SUB"))
