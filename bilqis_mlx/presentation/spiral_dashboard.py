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

from .renderer.core import Dashboard as Dashboard


from .renderer.commands import (
    RawLogStream as RawLogStream,
    _feed_event as _feed_event,
    train as train,
    watch as watch,
    main as main,
)

if __name__ == "__main__":
    main()
