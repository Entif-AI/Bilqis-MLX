"""Explicit source clause syntax; reviewed evidence supplies prerequisite meaning."""
import re

KEY = r'[ABC]\d{2}(?:\.\d+[a-z]?)*'
LINK_TEXT = r'\[[^\]]+\]\([^)]+\)'


def _short_edges(text, numbers):
    text = text.split('. OPEN', 1)[0].rstrip('.')
    through = re.fullmatch('(' + KEY + ') through (' + KEY + ')', text)
    if through:
        start, end = (re.fullmatch(r'(.+\.)(\d+)', key) for key in through.groups())
        if not start or not end or start[1] != end[1]:
            return None
        first, last = int(start[2]), int(end[2])
        if first > last or last - first + 1 > len(numbers):
            return None
        return tuple(start[1] + str(n) for n in range(first, last + 1))
    if re.fullmatch(KEY + r'(?:,\s*' + KEY + ')*', text):
        return tuple(re.findall(KEY, text))
    return None


def _linked_edges(text, numbers):
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
    if not links:
        return None
    edges = []
    for label, url in links:
        match = re.fullmatch('(' + KEY + r')\s*#(\d+)', label)
        if (not match or numbers.get(match[1]) != int(match[2])
                or url != 'https://github.com/Entif-AI/Bilqis-MLX/issues/' + match[2]):
            return None
        edges.append(match[1])
    return tuple(edges)


def _genesis_custody_prerequisites(text, numbers):
    keys = ('B13.1', 'B13.4')
    if any(type(numbers.get(key)) is not int for key in keys):
        return None
    expected = (
        '## Direct prerequisites\n\n'
        f'- B13.1 #{numbers["B13.1"]} immutable bundle/pointer custody interface.\n'
        f'- B13.4 #{numbers["B13.4"]} / B01 parameter-schema and initializer authority.\n\n'
        'Open parent state alone is not a blocker when the required exact interface is already present '
        'on reviewed unified; final turn-in must record the actual consumed receipts.'
    )
    return (keys, (885, 802)) if text == expected else None


def _released_schema_serialization_prerequisites(text, numbers):
    expected = (
        '## Dependency / handoff\n'
        'Consumes A01 release identity and accepted A03/A04 schema serialization. '
        'B07.1 #456 must consume this witness together with the existing source-owned A13 grant machinery; '
        'B08.1 #460 must additionally bind complete rights/revocation/generation dependencies into its cache/read identity.\n\n'
        'No neural/source admission or training is authorized by this issue.'
    )
    if text != expected or type(numbers.get('A01')) is not int:
        return None
    return (('A01',), (551,))


def _a05_source_binding_prerequisites(text, numbers, source_hashes, implementation_receipts):
    expected = (
        'Child of A05 #357; prerequisite for canonical B11.1a producer #586 and downstream B05.4 #577. '
        'A05 `SourceAtom` currently carries only index/token/source reference; B03 `CompiledEmbeddingVectors` '
        'accepts caller-supplied raw atom vectors, so a real B11 h0 producer cannot prove that those vectors '
        'came from admitted A01/B02 semantic identities.'
    )
    keys = ('A01', 'A13')
    if (text != expected
            or numbers.get('A01') != 345
            or numbers.get('A13') != 354
            or source_hashes.get('A05.5.comment-6838106985') != '85e237de0d9755337655d7224a9a20064c57ef2c21ddccf293d45e7bcb5774f3'
            or source_hashes.get('A05.5.pr-618') != '6cf936f2c092e318c41ce71748da3c2bfcbddf4be0863afa78e0a49341aa2991'
            or 618 not in implementation_receipts):
        return None
    return keys, ()


def _a08_family_integration_prerequisites(text, numbers, source_hashes, implementation_receipts):
    expected = (
        '**Direct prerequisites:** A08.1b.1 through A08.1b.4. '
        'OPEN parent status alone is not a blocker when an exact reviewed branch receipt exists.'
    )
    keys = ('A08.1a', 'A08.1b.1', 'A08.1b.2', 'A08.1b.3', 'A08.1b.4')
    expected_numbers = (417, 553, 554, 555, 556)
    if (text != expected
            or tuple(numbers.get(key) for key in keys) != expected_numbers
            or source_hashes.get('A08.1b.5.comment-6838107336') != '20d67eb8750d1554e872086c3c4689e7b3103f4e5e79e642241e21f51fdffb3d'
            or source_hashes.get('A08.1b.5.pr-657') != 'c43309ecd54f1516b86a89f06c355f31bde98c4171632dd6660324794ddf535e'
            or 657 not in implementation_receipts):
        return None
    return keys, ()


def _b11_cycle_prerequisites(text, numbers, source_hashes):
    expected = (
        '## Dependency-cycle rule\n'
        'This child is deliberately carved out of B11.1 so it can precede B05 parent acceptance. '
        'It consumes the accepted B01 topology/parameter registry, reviewed B04 attention/block primitives, '
        'and the already-implemented B05 numerical selector contract as a downstream numerical operation. '
        'It **must not depend on B05.4 provenance acceptance** or B13 final generation custody. '
        'Full B11.1 remains responsible for complete model assembly after the surrounding owners are accepted.'
    )
    keys = ('B01', 'B04', 'A05.5')
    if (text != expected or any(type(numbers.get(key)) is not int for key in keys)
            or numbers['A05.5'] != 594
            or source_hashes.get('B11.1a.comment-6505193864') != '7e495f4438216b078f8551a31b046982f35e6b027fc68df8def65080b028aeb0'):
        return None
    return (keys, (552, 618))


def _b02_child_handle_prerequisites(text, numbers):
    expected = (
        '## Dependency / handoff\n'
        'Consumes B01 parameter/feature authority, actual A05 compiled child handles, and the A05.4 partial-visible-forest contract. '
        'Completion unblocks the neural half of B03.3 #444.\n\n'
        'No source admission, ABI allocation, or durable training is authorized by this issue.'
    )
    keys = ('B01', 'A05.4')
    if text != expected or any(type(numbers.get(key)) is not int for key in keys):
        return None
    return (keys, (546,))


def _a08_formal_operator_prerequisites(text, numbers):
    expected = (
        '**Direct prerequisites:** A08.1a, A07.1, A07.2, A13. '
        'OPEN parent status alone is not a blocker when an exact reviewed branch receipt exists.'
    )
    keys = ('A08.1a', 'A07.1', 'A07.2', 'A13')
    if text != expected or any(type(numbers.get(key)) is not int for key in keys):
        return None
    return (keys, (546,))


def _current_a05_compiler_prerequisites(text, numbers):
    expected = (
        '## Dependency / handoff\n'
        'Consumes accepted A03/A04/A13 and current A05 compiler receipts. '
        'On completion, B03.3 #444 must rerun its child-only future-isolation and nested-gradient proof against this exact source contract.\n\n'
        'No live learner or durable optimizer start is authorized by this issue.'
    )
    keys = ('A03', 'A04', 'A13')
    if text != expected or any(type(numbers.get(key)) is not int for key in keys):
        return None
    return (keys, (546,))


def _producer_correction(clause, numbers):
    if not re.search(r'^## Producer-authority correction(?: |$)', clause, re.M):
        return None
    inputs = re.findall(r'^Consumes (' + KEY + r') topology/tensor identities and (' + KEY + r') execution/cache identity\.', clause, re.M)
    producers = re.findall(r'^The missing producer authority is now owned by (' + LINK_TEXT + r')\. Until #(\d+) is implemented and independently reviewed,', clause, re.M)
    if len(inputs) != 1 or len(producers) != 1:
        return None
    edges = _linked_edges(producers[0][0], numbers)
    if edges is None or len(edges) != 1 or numbers[edges[0]] != int(producers[0][1]):
        return None
    return (*inputs[0], *edges), ()


def _parent_amendment(clause, numbers):
    if not re.search(r'^## Recursive blocker decomposition(?: |$)', clause, re.M):
        return None
    section = re.search(r'^## Direct prerequisites\n(.*?)(?=^## |\Z)', clause, re.M | re.S)
    declarations = re.findall(r'^(' + KEY + r') now has a prerequisite implementation child: (' + LINK_TEXT + ')', clause, re.M)
    if section is None or len(declarations) != 1:
        return None
    parent, link = declarations[0]
    original = _linked_edges(section[1].split('Original ', 1)[0], numbers)
    child = _linked_edges(link, numbers)
    if original is None or child is None or len(child) != 1:
        return None
    mandatory = r'(?:^|\. )' + re.escape(parent) + ' must consume the accepted #' + str(numbers[child[0]]) + r' producer\b'
    if not re.search(mandatory, clause, re.M):
        return None
    return (*original, *child), ()


def parse_clause(clause, numbers, source_hashes=None, implementation_receipts=(), entry_key=None):
    source_hashes = source_hashes or {}
    if entry_key == 'A05.5':
        return _a05_source_binding_prerequisites(
            clause, numbers, source_hashes, implementation_receipts)
    if entry_key == 'A08.1b.5':
        return _a08_family_integration_prerequisites(
            clause, numbers, source_hashes, implementation_receipts)
    b11_cycle = _b11_cycle_prerequisites(clause, numbers, source_hashes)
    if b11_cycle is not None:
        return b11_cycle
    b02_child = _b02_child_handle_prerequisites(clause, numbers)
    if b02_child is not None:
        return b02_child
    a08_formal = _a08_formal_operator_prerequisites(clause, numbers)
    if a08_formal is not None:
        return a08_formal
    prefix = '**Direct prerequisites:** '
    if clause.startswith(prefix):
        edges = _short_edges(clause[len(prefix):], numbers)
        return None if edges is None else (edges, ())
    if clause.startswith('## Direct prerequisites\n'):
        edges = _linked_edges(clause, numbers)
        if edges is not None:
            return edges, ()
        return _genesis_custody_prerequisites(clause, numbers)
    released_schema = _released_schema_serialization_prerequisites(clause, numbers)
    if released_schema is not None:
        return released_schema
    a05_compiler = _current_a05_compiler_prerequisites(clause, numbers)
    if a05_compiler is not None:
        return a05_compiler
    match = re.match(r'Direct prerequisites: merged #(\d+)/#(\d+); exact qualified #(\d+)/#(\d+) receipts for final composition turn-in; existing (' + KEY + r'(?:/' + KEY + r')*) source interfaces\.', clause)
    if match:
        return tuple(match[5].split('/')), tuple(int(match[i]) for i in range(1, 5))
    return _producer_correction(clause, numbers) or _parent_amendment(clause, numbers)


