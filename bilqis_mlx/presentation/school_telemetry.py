"""Grade-independent, read-only School50 telemetry projection.

Legacy Grade A events adapt to this contract. New grades can emit SCHOOL_*
events without teaching the dashboard their particular lesson vocabulary.
No scoring here is passed back to a teacher, model, or curriculum admission.
"""
from __future__ import annotations

from bilqis_mlx.presentation.progression_projection import GraduationProjection
from bilqis_mlx.presentation.growth_projection import GrowthProjection
from collections import defaultdict
from bilqis_mlx.compatibility.telemetry_events import (
    historical_capability_grade,
    historical_course_admission,
    historical_event_grade,
    historical_event_kind,
    historical_live_exam,
    historical_withheld_inventory_change_explains,
)

from .school50.labels import (
    _signal_label as _signal_label,
    _teacher_decision_text as _teacher_decision_text,
    _warning_text as _warning_text,
    _candidate_result_reason as _candidate_result_reason,
    _candidate_admission_text as _candidate_admission_text,
    _association_text as _association_text,
    _instruction_method_text as _instruction_method_text,
    _SIGNAL_LABELS as _SIGNAL_LABELS,
    _REASON_LABELS as _REASON_LABELS,
)
from .school50.diagnostics import (
    _candidate_retention_row as _candidate_retention_row,
    _diagnostic_system_rows as _diagnostic_system_rows,
    _teacher_outcome_text as _teacher_outcome_text,
    _measured_teacher_outcomes as _measured_teacher_outcomes,
    _measured_outcome_changes as _measured_outcome_changes,
    _unmeasured_outcome_counts as _unmeasured_outcome_counts,
)
from .school50.formatting import (
    _display as _display,
    _inventory_scope as _inventory_scope,
    _scaled_lr as _scaled_lr,
    _whole as _whole,
    _score_quad as _score_quad,
    _delta as _delta,
    _percent as _percent,
    _count as _count,
    _source_provenance as _source_provenance,
    ExamScore as ExamScore,
)
from .school50.tables import (
    LETTER_TABLES as LETTER_TABLES,
    EVENT_KINDS as EVENT_KINDS,
    TELEMETRY_VERSION as TELEMETRY_VERSION,
)
from .school50.curriculum import CurriculumProjection
from .school50.candidates import CandidatesProjection
from .school50.exams import ExamsProjection
from .school50.summary import SummaryProjection
from .school50.evidence import EvidenceProjection

class SchoolTelemetry(CurriculumProjection, CandidatesProjection, ExamsProjection, SummaryProjection, EvidenceProjection):
    """Incremental projection; START/latest/best scores are receipt-backed."""

    def __init__(self, board, *, active_grades=(), champions=None):
        self.board = board
        self.grades = list(active_grades)
        self.champions = champions or {}
        self.start = {}   # (grade, complete-rubric, scope) -> execution-start ExamScore
        self.latest = {}
        self.best = {}
        self.last_cap = {}  # (capability, complete-rubric) -> (correct,total)
        self.start_cap = {}
        self.growth = GrowthProjection(active_grades)
        self.last_source_training = {}  # capability -> (accuracy, optimizer_step)
        self.exam_cohorts = {}  # (grade, semantic rubric) -> last sampled cohort
        self.reported_scope_inventory = {}
        self.scope_variants = {}
        # Whole-student exam scores are distinct from separate per-grade bests.
        self.cumulative_best = {}  # (grades, rubric, scope) -> (correct, total, step)
        self.cumulative_latest = None  # (key, correct, total, step, status)
        self.score_era = 0
        self.era_cohorts = defaultdict(set)
        self.visits = 0
        self.last_exam_grade = None
        self.execution_start_step = None
        self.live_projected_generations = set()
        self.teacher_policy_health = {}
        self.graduations = GraduationProjection(); self.board.state["graduations"] = self.graduations.summary()
        self.board.grade_program = tuple(self.grades)

    def _grade(self, name):
        if name not in self.grades:
            self.grades.append(name)
            self.board.grade_program = tuple(self.grades)

    def ingest(self, event: dict):
        if (event.get("event", "").startswith("SCHOOL_") and
                event.get("telemetry_schema", TELEMETRY_VERSION) != TELEMETRY_VERSION):
            raise ValueError("SCHOOL_TELEMETRY_UNSUPPORTED_SCHEMA")
        kind = (EVENT_KINDS.get(event.get("event")) or
                historical_event_kind(event.get("event")))
        if kind is None:
            return
        grade = event.get("grade") or historical_event_grade(event["event"])
        if kind not in {"init", "resource"} and not grade:
            raise ValueError("SCHOOL_TELEMETRY_GRADE_REQUIRED")
        if grade:
            self._grade(grade)
        {
            "init": self._init,
            "curriculum": self._curriculum,
            "start": self._start,
            "visit": self._visit,
            "exam": self._exam,
            "stop": self._stop,
            "sentinel": self._sentinel,
            "soup": self._soup,
            "family": self._family,
            "resource": self._resource,
            "capability_best": self._capability_best,
            "candidate": self._candidate,
            "qualification": self._qualification,
            "progress": self._progress,
            "autonomy": self._autonomy,
        }[kind](grade, event)
        self.board.state["graduations"] = self.graduations.observe(event)
