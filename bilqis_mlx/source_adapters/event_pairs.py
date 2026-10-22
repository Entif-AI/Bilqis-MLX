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
OPTION = 'source.event-query-and-prerequisite-contrast/v1'
QUERY_PAIR_SIZE = 2


def _pools(graph, capability):
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
    return pools


def draw(source_root, graph, *, seed, each=12, capability, **_):
    pools = _pools(graph, capability)
    rng = random.Random(digest((GENERATOR, seed, capability)))
    paired = list(rng.choice(_contrast_pairs(pools))) if each >= QUERY_PAIR_SIZE else []
    rng.shuffle(paired)
    used = {row['id'] for row in paired}
    selected = {gold: iter(rng.sample([row for row in pool if row['id'] not in used],
                                    (each + int(gold)) // 2 - int(bool(paired))))
                for gold, pool in pools.items()}
    return (*paired, *(next(selected[index % 2 == 0])
                       for index in range(each - len(paired))))


def _contrast_pairs(pools):
    by_id = {row['id']: row for pool in pools.values() for row in pool}
    result = []
    for row in pools[True]:
        record = row['record']
        other = next(event[0] for event in record['events'] if event[0] != record['query'])
        opposite = by_id[digest({**record, 'query': other})]
        if opposite['gold'] != row['gold']:
            result.append((row, opposite))
    return result


def check(row, **kwargs):
    return (row.get('generator') == GENERATOR and
            frames.check({**row, 'generator': frames.GENERATOR}, **kwargs))


def enrich(*, graph, capability, seed, option_id, prerequisites=None, **_):
    if option_id != OPTION:
        raise ValueError(intro.OPTION_NOT_RELEASED)
    pairs = _contrast_pairs(_pools(graph, capability))
    rng = random.Random(seed)
    result = []
    for pair in rng.sample(pairs, 8):
        ordered = list(pair)
        rng.shuffle(ordered)
        result.extend(ordered)
    target_rows = tuple(result)
    for prior in (frames.SPECS[capability][1] if prerequisites is None else prerequisites):
        if prior in frames.SPECS and prior != capability:
            lookup = {row['id']: row for pool in _pools(graph, prior).values() for row in pool}
            result.extend(lookup[digest({**row['record'], 'capability': prior})]
                          for row in target_rows)
    return tuple(result)


def registered_adapter():
    previous = frames.registered_adapter().descriptor
    fingerprint = digest((previous.implementation_sha256,
                          hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    return RegisteredSourceAdapter(SourceAdapter(
        'source.issue349.event-pairs/v1', GENERATOR, previous.accepted_oracle_ids,
        fingerprint, variation_axes=('two-event-lookup', 'query-contrast', 'declared-prerequisite-contrast', *previous.variation_axes),
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
        source_root=source_root, graph=graph, verification_seed=349202,
        predecessor=current)
