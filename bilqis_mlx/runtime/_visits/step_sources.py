"""Source and preservation rows for each optimizer step."""
from __future__ import annotations


def initialize(d, s):
    s.last_loss = 0.0
    s.last_norm = 0.0
    s.methodology_steps = []
    s.methodology_unavailable = None
    s.replayed_misses = 0
    s.champion_prioritized = 0
    s.enrichment_examples = 0
    s.policy_control_receipts = []
    s.step_before = int(s.optimizer.state["step"].item())
    s.fragile_fixed_rows = ()
    if s.learning_settings is not None:
        from bilqis_mlx.learning.fragile_replay import load_replay_rows
        with d._runtime_timing_trace.trace_span("FRAGILE_REPLAY_LOAD", capability=s.cap):
            s.fragile_fixed_rows = load_replay_rows(
                s.run_dir, s.receipt,
                capabilities=d._profiles_retention.fragile_preservation_capabilities())
    s.old_capabilities, s.retention_support_capabilities = d._visit_retention_scope(
        s.run_dir, s.receipt, s.course, s.school, s.cap, s.learning_settings,
        candidate_steps=s.candidate_steps, fragile_fixed_rows=s.fragile_fixed_rows)
    s.delivered_autonomy_rows = []
    s.autonomy_option_specimen_ids = set()
    s.prefetch_futures = {}
    s.prefetch_enabled = bool(
        s.learning_settings is not None and s.source_prefetch_executor is not None and
        s.source_prefetch_workers > 0 and s.autonomy_teaching_option is None)
    if not s.prefetch_enabled:
        return
    from bilqis_mlx.runtime.source_prefetch import SCHEMA, prepare_step_sources
    s.source_prefetch_schema = SCHEMA
    s.prepare_step_sources = prepare_step_sources
    admitted = set(d._curriculum_scheduler.assessment_capabilities(
        d._runtime_release_adoption._schedule_for_receipt(s.run_dir, s.receipt, s.course),
        s.school))
    s.fragile_requested = tuple(
        name for name in d._profiles_retention.fragile_preservation_capabilities()
        if name in admitted)
    s.course_digest = s.course.digest()
    s.graph_digest = s.receipt.get("semantic_graph_sha256") or d._runtime_state._fingerprint(s.graph)
    for step_index in range(min(s.source_prefetch_workers, s.candidate_steps)):
        _submit(d, s, step_index)


def _request(d, s, step_index):
    from bilqis_mlx.runtime.source_prefetch import visit_source_request
    return visit_source_request(
        step_index, s.policy, s.old_capabilities, s.school,
        s.retention_support_capabilities, s.receipt, s.cap, s.fragile_requested,
        s.boolean_association_bridge, s.executable_release, s.course_digest,
        s.graph_digest, s.step_before, s.course, s.graph, s.source_root,
        s.batch_size, s.fragile_fixed_rows)


def _submit(d, s, step_index):
    request = _request(d, s, step_index)
    d._runtime_timing_trace.trace_mark(
        "STEP_SOURCE_PREFETCH_SUBMIT", capability=s.cap, visit_step=step_index + 1,
        identity=request["identity"])
    s.prefetch_futures[step_index] = (
        request, s.source_prefetch_executor.submit(s.prepare_step_sources, request))


def for_step(d, s, step):
    prepared = None
    if s.prefetch_enabled:
        request, future = s.prefetch_futures.pop(step)
        with d._runtime_timing_trace.trace_span(
                "STEP_SOURCE_PREFETCH_WAIT", capability=s.cap, visit_step=step + 1,
                identity=request["identity"]):
            prepared = future.result()
        if (prepared.get("schema") != s.source_prefetch_schema or
                prepared.get("identity") != request["identity"]):
            raise ValueError("HUMAN_TRAINER_SOURCE_PREFETCH_IDENTITY_DRIFT")
        next_step = step + s.source_prefetch_workers
        if next_step < s.candidate_steps:
            _submit(d, s, next_step)
        fresh = list(prepared["fresh"])
    else:
        with d._runtime_timing_trace.trace_span("STEP_SOURCE_DRAW", capability=s.cap,
                                                visit_step=step + 1):
            if s.autonomy_teaching_option is None:
                fresh = d._runtime_assessment._draw_live_rows(
                    s.source_root, s.graph,
                    seed=d._runtime_state._seed(s.receipt, capability=s.cap, step=step + 1),
                    capability=s.cap, each=max(32, s.batch_size), course=s.course,
                    executable_release=s.executable_release)
            else:
                from bilqis_mlx.factory.teaching import draw_teaching_option_rows
                fresh = list(draw_teaching_option_rows(
                    s.source_root, s.graph, s.executable_release,
                    d._source_adapters_school.live_source_registry(), capability=s.cap,
                    option_id=s.autonomy_teaching_option,
                    seed=d._runtime_state._seed(s.receipt, capability=s.cap, step=step + 1),
                    each=max(32, s.batch_size)))
                s.autonomy_option_specimen_ids.update(row["id"] for row in fresh)
    option_rows = tuple(fresh)
    fresh.extend(s.priority)
    preservation = retention_support = ()
    if s.learning_settings is not None:
        if prepared is not None:
            preservation = tuple(prepared["preservation"])
            retention_support = tuple(prepared["retention_support"])
        else:
            with d._runtime_timing_trace.trace_span(
                    "STEP_FRAGILE_PRESERVATION", capability=s.cap, visit_step=step + 1):
                preservation = d._runtime_candidate_evidence._fresh_fragile_preservation_rows(
                    s.run_dir, s.source_root, s.graph, s.receipt, s.course, s.school,
                    s.cap, step=step + 1, batch_size=s.batch_size,
                    fixed_rows=s.fragile_fixed_rows, executable_release=s.executable_release)
            if s.retention_support_capabilities:
                support_capability = s.retention_support_capabilities[
                    step % len(s.retention_support_capabilities)]
                with d._runtime_timing_trace.trace_span(
                        "STEP_RETENTION_SUPPORT", capability=s.cap,
                        support_capability=support_capability, visit_step=step + 1):
                    support_rows = d._runtime_assessment._draw_live_rows(
                        s.source_root, s.graph, course=s.course,
                        executable_release=s.executable_release, capability=support_capability,
                        each=max(s.batch_size, 6),
                        seed=d._runtime_state._seed(
                            s.receipt, capability="RETENTION_SUPPORT:" + support_capability,
                            step=step + 1))
                    retention_support = d._runtime_candidate_evidence._select_fresh_retention_support_rows(
                        support_rows, rotation=s.school.visits + step)
    return prepared, fresh, option_rows, preservation, retention_support
