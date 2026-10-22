"""A two-event experimental learning slice; original four-event probes survive."""
from dataclasses import replace
import hashlib
from itertools import permutations, product
from pathlib import Path
import random

from . import event_frames as frames, event_intro as intro
from ..factory.adapters import RegisteredSourceAdapter
from ..factory.executable_release import compile_executable_factory_release
from ..factory.model import SourceAdapter
from ..vocabulary_growth import digest

GENERATOR = 'bilqis.issue349.event-pairs/v1'


def draw(source_root, graph, *, seed, each=12, capability, **_):
    frames.source_senses()
    ids = {token: index for index, token in enumerate(graph['tokens'])}
    pools = {True: [], False: []}
    for names in permutations(('E0', 'E1', 'E2', 'E3'), 2):
        for states in product((False, True), repeat=4):
            for query in names:
                record = dict(task=frames.DIALECT, capability=capability, query=query,
                    events=[[names[0], *states[:2]], [names[1], *states[2:]]])
                identity = digest(record)
                gold = frames.independent_answer(record)
                pools[gold == 'TRUE'].append(dict(id=identity, source_id=identity,
                    capability=capability, answer_kind='binary', gold=gold, record=record,
                    tokens=[ids[symbol] for symbol in frames.encode(record)],
                    root=frames.SYMBOLS[capability], generator=GENERATOR, oracle=frames.ORACLE,
                    source_sense_id=frames.SPECS[capability][0]))
    rng = random.Random(digest((GENERATOR, seed, capability)))
    selected = {gold: iter(rng.sample(pool, (each + int(gold)) // 2))
                for gold, pool in pools.items()}
    return tuple(next(selected[index % 2 == 0]) for index in range(each))


def check(row, **kwargs):
    return (row.get('generator') == GENERATOR and
            frames.check({**row, 'generator': frames.GENERATOR}, **kwargs))


def enrich(**kwargs):
    return tuple({**row, 'generator': GENERATOR} for row in intro.enrich(**kwargs))


def registered_adapter():
    previous = intro.registered_adapter().descriptor
    fingerprint = digest((previous.implementation_sha256,
                          hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    return RegisteredSourceAdapter(SourceAdapter(
        'source.issue349.event-pairs/v1', GENERATOR, previous.accepted_oracle_ids,
        fingerprint, variation_axes=('two-event-lookup', *previous.variation_axes),
        teaching_option_ids=previous.teaching_option_ids), draw, check, enrich=enrich,
        witness=lambda row, obligation, **kwargs: check(row, **kwargs) and
            obligation.key in frames.SPECS[row['capability']][1])


def compile_successor(current, graph, *, source_root, source_registry, answer_registry):
    bindings = replace(current.source_bindings, bindings=tuple(
        replace(binding, generator_id=GENERATOR)
        if binding.capability_id in frames.SPECS else binding
        for binding in current.source_bindings.bindings))
    return compile_executable_factory_release(
        current.curriculum, bindings, current.profile, source_registry, answer_registry,
        source_root=source_root, graph=graph, verification_seed=349202,
        predecessor=current)
