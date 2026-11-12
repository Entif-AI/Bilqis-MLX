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


def parse_clause(clause, numbers):
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
    match = re.match(r'Direct prerequisites: merged #(\d+)/#(\d+); exact qualified #(\d+)/#(\d+) receipts for final composition turn-in; existing (' + KEY + r'(?:/' + KEY + r')*) source interfaces\.', clause)
    if match:
        return tuple(match[5].split('/')), tuple(int(match[i]) for i in range(1, 5))
    return _producer_correction(clause, numbers) or _parent_amendment(clause, numbers)


