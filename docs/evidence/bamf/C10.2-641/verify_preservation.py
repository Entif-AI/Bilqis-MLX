"""Reproduce #641 source/test preservation against the accepted pre-split owner."""
import ast
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import importlib
from pathlib import Path
import pickle
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


def require_receipt(observed, path):
    if observed != json.loads(path.read_text()):
        raise ValueError('committed preservation receipt differs from inspected source')


def verify_imports_and_pickle():
    module_name = 'bilqis_mlx.runtime.block_attnres'
    module = importlib.import_module(module_name)
    contracts = importlib.import_module('bilqis_mlx.runtime.depth_contracts')
    for owner, filename in ((module, 'block_attnres.py'), (contracts, 'depth_contracts.py')):
        if Path(owner.__file__).resolve() != (PRODUCTION / filename).resolve():
            raise ValueError('canonical import owner drift: ' + filename)
    identities = {}
    for node in original('bilqis_mlx/runtime/block_attnres.py').body:
        if not (isinstance(node, ast.ClassDef) or
                isinstance(node, ast.FunctionDef) and not node.name.startswith('_')):
            continue
        value = getattr(module, node.name)
        if getattr(contracts, node.name, value) is not value:
            raise ValueError('relocated alias identity drift: ' + node.name)
        historical = ('c' + module_name + '\n' + node.name + '\np0\n.').encode()
        if (value.__module__ != module_name or pickle.loads(historical) is not value
                or pickle.dumps(value, protocol=0) != historical):
            raise ValueError('public import/pickle identity drift: ' + node.name)
        identities[node.name] = module_name + '.' + node.name
    return identities


def verify():
    reports = {}
    inspected = [Path(__file__), Path(__file__).with_name('test_verify_preservation.py')]
    cases = (
        ('production', 'bilqis_mlx/runtime/block_attnres.py', PRODUCTION, False),
        ('tests', 'bilqis_mlx/runtime/tests/test_block_attnres.py', TESTS, True),
    )
    for label, old_path, directory, recursive in cases:
        before = definitions([original(old_path)], recursive=recursive)
        paths = sorted(directory.glob('*.py'))
        inspected.extend(paths)
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
    hashes = {str(path.relative_to(Path.cwd()) if path.is_absolute() else path):
              hashlib.sha256(path.read_bytes()).hexdigest() for path in inspected}
    return {'baseline': BASE, 'reports': reports, 'inspected_file_sha256': hashes,
            'import_pickle_identities': verify_imports_and_pickle()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='compare to committed receipt')
    args = parser.parse_args()
    result = verify()
    if args.check:
        require_receipt(result, Path(__file__).with_name('preservation.json'))
        print('PRESERVATION_RECEIPT_OK')
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
