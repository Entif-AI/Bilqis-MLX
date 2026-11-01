"""Read-only BAMF operator evidence boundary."""
from .base import _spec


class BAMF_OPERATOR:
    INVALID = _spec(
        ("SCHOOL", "BAMF_OPERATOR", "INVALID"),
        owner="presentation.atlas_metrics",
        title="BAMF operator evidence is invalid",
        message_template="The BAMF operator observation is invalid: {reason}",
        disposition="PRESERVE_AND_INSPECT",
        next_action="Keep the last valid view and retained run unchanged; reconcile the source census, measurement and identity bindings.",
    )
