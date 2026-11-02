"""Disk gate immediately before an operator visit."""
import bilqis_mlx.runtime.disk as disk
import bilqis_mlx.runtime.timing_trace as timing_trace


def operator_disk_ready(run_dir, reserve_gib, visits):
    with timing_trace.trace_span("DISK_HEADROOM", visit_index=visits + 1):
        budget = disk.headroom_snapshot(run_dir, required_bytes=600_000_000,
                                   reserve_gib=reserve_gib)
    if not budget["sufficient"]:
        return False
    # Retain the original fail-closed checkpoint preflight against
    # disk changes between telemetry and the actual write boundary.
    with timing_trace.trace_span("DISK_HEADROOM_ASSERT", visit_index=visits + 1):
        disk.assert_headroom(run_dir, required_bytes=600_000_000,
                        reserve_gib=reserve_gib)
    return True
