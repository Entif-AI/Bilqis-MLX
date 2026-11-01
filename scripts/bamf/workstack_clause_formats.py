"""Explicit source clause syntax; reviewed evidence supplies prerequisite meaning."""
import re

KEY = r'[ABC]\d{2}(?:\.\d+[a-z]?)*'


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


def parse_clause(clause, numbers):
    prefix = '**Direct prerequisites:** '
    if clause.startswith(prefix):
        edges = _short_edges(clause[len(prefix):], numbers)
        return None if edges is None else (edges, ())
    if clause.startswith('## Direct prerequisites\n'):
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', clause)
        if not links:
            return None
        edges = []
        for label, url in links:
            match = re.fullmatch('(' + KEY + r')\s*#(\d+)', label)
            if (not match or numbers.get(match[1]) != int(match[2])
                    or url != 'https://github.com/Entif-AI/Bilqis-MLX/issues/' + match[2]):
                return None
            edges.append(match[1])
        return tuple(edges), ()
    match = re.match(r'Direct prerequisites: merged #(\d+)/#(\d+); exact qualified #(\d+)/#(\d+) receipts for final composition turn-in; existing (' + KEY + r'(?:/' + KEY + r')*) source interfaces\.', clause)
    if match:
        return tuple(match[5].split('/')), tuple(int(match[i]) for i in range(1, 5))
    return None


