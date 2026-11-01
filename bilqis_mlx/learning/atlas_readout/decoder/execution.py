"""Replay the causal commit prefix before accepting logits as supervision."""
from ..control import ControlAction
from ..decisions import (
    DecodeStatus, start_decoding, ready_decisions, allowed_values, commit_decisions,
)
from ..frames import publish_frame
from ..records import invalid


def validate_execution(output):
    if len(output.decisions) != len(output.committed):
        invalid()
    state = start_decoding(output.plan)
    offset = 0
    while offset < len(output.committed):
        ready = ready_decisions(state)
        if not ready:
            invalid()
        ending = output.committed[offset].value is ControlAction.END_FRAME
        count = 1 if ending else len(ready)
        commits = output.committed[offset:offset + count]
        records = output.decisions[offset:offset + count]
        if len(commits) != count:
            invalid()
        specs = {decision.decision_id: decision for decision in ready}
        if not ending and tuple(c.decision_id for c in commits) != tuple(specs):
            invalid()
        for record, commit in zip(records, commits):
            spec = specs.get(commit.decision_id)
            if (spec is None or record.decision_id != commit.decision_id
                    or record.kind is not spec.kind
                    or len(record.candidates) != len(allowed_values(state, commit.decision_id))
                    or any(type(actual) is not type(legal) or actual != legal
                           for actual, legal in zip(record.candidates,
                               allowed_values(state, commit.decision_id)))):
                invalid()
        state = commit_decisions(state, commits)
        offset += count
    if output.status not in (DecodeStatus.COMPLETE, DecodeStatus.PARTIAL, DecodeStatus.UNRESOLVED):
        invalid()
    if output.status is not DecodeStatus.UNRESOLVED and output.status is not state.status:
        invalid()
    if output.frame is not None and output.frame != publish_frame(state):
        invalid()
