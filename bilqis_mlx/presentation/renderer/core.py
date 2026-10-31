"""Stable Dashboard class composition shared by module and command entry points."""
from __future__ import annotations

from collections import deque
import sys
import time
from .tables import TABLES
from .champions import ChampionsView
from .history import HistoryView
from .events import EventsView
from .sections import SectionsView
from .wide import WideView
from .render import RenderView
from .snapshots import SnapshotsView


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


Dashboard.__module__ = "bilqis_mlx.presentation.spiral_dashboard"
