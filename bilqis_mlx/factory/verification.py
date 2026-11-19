"""Compatibility exports; independent truth and codec checks are source-owned."""
from ..source_adapters.copular import check_copular
from ..verification.copular import VERSION as COPULAR_ORACLE
from ..verification.event_frames import (
    VERSION as EVENT_FRAME_ORACLE, independent_answer as event_frame_answer,
)
