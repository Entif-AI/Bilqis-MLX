"""Read-only, top-style operator display for staged School50 training.

The dashboard is deliberately OUTSIDE the model's hashed training recipe.
It renders typed diagnostic records in bounded category buffers. A terminal
redraw never writes a checkpoint, modifies a gate or discards the raw text log.
"""
from __future__ import annotations

from collections import deque
import sys
import time
from .renderer.tables import TABLES

from .renderer.tables import (
    Column as Column,
    TABLES as TABLES,
    WIDE_MIN_WIDTH as WIDE_MIN_WIDTH,
    WIDE_MIN_HEIGHT as WIDE_MIN_HEIGHT,
    WIDE_SEP as WIDE_SEP,
    WIDE_PANES as WIDE_PANES,
    WIDE_ROW_FRACTIONS as WIDE_ROW_FRACTIONS,
)
from .renderer.scores import (
    _next_grade as _next_grade,
    _score_tuple as _score_tuple,
    _nearest_percent as _nearest_percent,
    _compact_score_line as _compact_score_line,
    _right_grew as _right_grew,
    _compact_summary_outcome as _compact_summary_outcome,
    _score_summary as _score_summary,
    _difference as _difference,
    _pp as _pp,
    _metric as _metric,
)
from .renderer.system import (
    _SYSTEM_KIND_CODES as _SYSTEM_KIND_CODES,
    _system_kind as _system_kind,
    _compact_diagnostic as _compact_diagnostic,
    _compact_cap_best as _compact_cap_best,
    _compact_system_detail as _compact_system_detail,
)
from .renderer.layout import (
    _clean as _clean,
    _step_exam as _step_exam,
    _cell as _cell,
    _human_duration as _human_duration,
    _header_table as _header_table,
    _columns as _columns,
    _table_line as _table_line,
    _section_heading as _section_heading,
    _right_header as _right_header,
    _pane_widths as _pane_widths,
    _wide_columns as _wide_columns,
)
from .renderer.candidates import (
    _soup as _soup,
    _candidate_rows as _candidate_rows,
    _metric_delta as _metric_delta,
)
from .renderer.champions import ChampionsView
from .renderer.history import HistoryView
from .renderer.events import EventsView
from .renderer.sections import SectionsView
from .renderer.wide import WideView
from .renderer.render import RenderView
from .renderer.snapshots import SnapshotsView
from bilqis_mlx.state_dag import read_current as read_current, read_current_fields as read_current_fields

class Dashboard(ChampionsView, HistoryView, EventsView, SectionsView, WideView, RenderView, SnapshotsView):
    """Bounded category buffers; render depends only on input records and size."""
    def __init__(self,*,stream=None,clock=None,max_records=512,redraw=True,
                 title="BILQIS / SCHOOL50 V5",show_all_panels=False,
                 tables=TABLES,compact_header=False):
        self.stream=stream if stream is not None else sys.stdout
        self.clock=clock if clock is not None else time.monotonic
        self.started=self.clock()
        self.tables=tables
        self.rows={name:deque(maxlen=max_records) for name,_ in self.tables}
        # Some dashboards fold this evidence into another rendered section.
        # Preserve the bounded read-only source buffer even when it has no
        # standalone table.
        self.rows.setdefault("BRIDGE FAMILIES",deque(maxlen=max_records))
        self.state={}
        self.mode="LIVE"
        self.log_hint=""
        self.run_name=""
        self.time_budget_seconds=None
        self.title=title
        self.compact_header=compact_header
        self.show_all_panels=show_all_panels
        self.redraw_enabled=redraw
        self.dirty=False
        self.progress=None
        self._progress_source=None
        self.grade_program=None
        self.bridge_families=None
        self.champion_line=None
        self._champion_rows=[]
        self._champion_source=None
        self._champion_start_step=None
        self._champion_mtime_ns=None
        self.current_course={}
        self.current_graduation_line=None
        self.operator_lines=[]
        self._rate_step=None
        self._rate_time=None
        self._steps_per_min=None


from .renderer.commands import (
    RawLogStream as RawLogStream,
    _feed_event as _feed_event,
    train as train,
    watch as watch,
    main as main,
)

if __name__ == "__main__":
    main()
