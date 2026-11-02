"""Reproduce #641 source/test preservation against the accepted pre-split owner."""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess


BASE = 'cec6a8ee1659854c292dc59566d4d14a53b75ae5^'
PRODUCTION = Path('bilqis_mlx/runtime/_depth')
TESTS = Path('bilqis_mlx/runtime/tests/depth')


def original(path):
    return ast.parse(subprocess.check_output(['git', 'show', BASE + ':' + path], text=True))


def definitions(trees, *, recursive):
    result = defaultdict(Counter)

    def visit(node, scope=()):
        named = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        identity = scope + (node.name,) if named else scope
        if named and (not recursive or not isinstance(node, ast.ClassDef)):
            digest = hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()).hexdigest()
            result['.'.join(identity)][digest] += 1
        if recursive:
            for child in ast.iter_child_nodes(node):
                visit(child, identity)

    for tree in trees:
        for node in tree.body:
            visit(node)
    return dict(result)


def require_preserved(before, after):
    for name, digests in before.items():
        if digests - after.get(name, Counter()):
            raise ValueError('definition/decorator drift: ' + name)


def verify():
    reports = {}
    cases = (
        ('production', 'bilqis_mlx/runtime/block_attnres.py', PRODUCTION, False),
        ('tests', 'bilqis_mlx/runtime/tests/test_block_attnres.py', TESTS, True),
    )
    for label, old_path, directory, recursive in cases:
        before = definitions([original(old_path)], recursive=recursive)
        paths = sorted(directory.glob('*.py'))
        after = definitions([ast.parse(path.read_text()) for path in paths], recursive=recursive)
        require_preserved(before, after)
        sizes = {str(path): len(path.read_text().splitlines()) for path in paths}
        if any(size >= 240 for size in sizes.values()) or len(paths) > 12:
            raise ValueError(label + ': structural target violated')
        additions = {name: dict(counts - before.get(name, Counter()))
                     for name, counts in after.items()
                     if counts - before.get(name, Counter())}
        reports[label] = {'preserved_definitions': before, 'file_lines': sizes,
                          'additional_definitions': additions}
    from bilqis_mlx.runtime import block_attnres
    for name in ('DepthParameterView', '_DepthFeatureValues', 'DepthFrameFeatures', 'DepthSummary'):
        if getattr(block_attnres, name).__module__ != 'bilqis_mlx.runtime.block_attnres':
            raise ValueError('public class identity drift: ' + name)
    return {'baseline': BASE, 'reports': reports}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
