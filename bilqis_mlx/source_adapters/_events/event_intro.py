"""Optional single-event lessons over the unchanged four-event assessment.

The original provider stays executable. This successor adds simpler instruction
without changing root meanings, token identities or the independent oracle.
"""
from dataclasses import replace
import hashlib
from itertools import product
from pathlib import Path
import random

from . import event_frames as frames
from ..factory.adapters import RegisteredSourceAdapter
from ..factory.executable_release import compile_executable_factory_release
from ..factory.model import SourceAdapter
from ..vocabulary_growth import digest

GENERATOR = 'bilqis.issue349.event-frames-introduction/v1'
OPTION = 'source.event-single-observation/v1'
OPTION_NOT_RELEASED = 'FACTORY_TEACHING_OPTION_NOT_RELEASED'


def draw(source_root, graph, **kwargs):
    return tuple({**row, 'generator': GENERATOR}
                 for row in frames.draw(source_root, graph, **kwargs))


def check(row, **kwargs):
    return (row.get('generator') == GENERATOR and
            frames.check({**row, 'generator': frames.GENERATOR}, **kwargs))


def enrich(*, graph, capability, seed, option_id, **_):
    if option_id != OPTION or capability not in frames.SPECS:
        raise ValueError(OPTION_NOT_RELEASED)
    frames.source_senses()
    ids = {token: index for index, token in enumerate(graph['tokens'])}
    rows = []
    for name, before, after in product(('E0', 'E1', 'E2', 'E3'), (False, True), (False, True)):
        record = dict(task=frames.DIALECT, capability=capability,
                      events=[[name, before, after]], query=name)
        identity = digest(record)
        rows.append(dict(id=identity, source_id=identity, capability=capability,
            answer_kind='binary', gold=frames.independent_answer(record), record=record,
            tokens=[ids[symbol] for symbol in frames.encode(record)],
            root=frames.SYMBOLS[capability], generator=GENERATOR, oracle=frames.ORACLE,
            source_sense_id=frames.SPECS[capability][0]))
    random.Random(seed).shuffle(rows)
    return tuple(rows)


def registered_adapter():
    original = frames.registered_adapter().descriptor
    fingerprint = digest((original.implementation_sha256,
                          hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    return RegisteredSourceAdapter(SourceAdapter(
        'source.issue349.event-frames-introduction/v1', GENERATOR,
        original.accepted_oracle_ids, fingerprint,
        variation_axes=(*original.variation_axes, 'single-event-instruction'),
        teaching_option_ids=(OPTION,)), draw, check, enrich=enrich,
        witness=lambda row, obligation, **kwargs: check(row, **kwargs) and
            obligation.key in frames.SPECS[row['capability']][1])


def compile_successor(current, graph, *, source_root, source_registry, answer_registry):
    bindings = replace(current.source_bindings, bindings=tuple(
        replace(binding, generator_id=GENERATOR)
        if binding.capability_id in frames.SPECS else binding
        for binding in current.source_bindings.bindings))
    return compile_executable_factory_release(
        current.curriculum, bindings, current.profile, source_registry, answer_registry,
        source_root=source_root, graph=graph, verification_seed=349201,
        predecessor=current)
