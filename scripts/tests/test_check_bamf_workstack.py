"""Behavior of the BAMF dependency and shared-file ownership boundary."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'check_bamf_workstack.py'


def item(key, lane, dependencies=(), paths=()):
    return {'key': key, 'number': {'A01': 345, 'A02': 348, 'B01': 346, 'C01': 347, 'B13': 372}[key],
            'lane': lane, 'deps': list(dependencies), 'paths': list(paths),
            'body_sha256': 'a' * 64}


def run(items, children=None, expected_map=None, omit_registry=False, queues=None, mirror_deps=None, mirror_lines=None):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'workstack.json'
        path.write_text(json.dumps({'schema': 'bilqis.bamf.workstack/v1',
                                    'version': '0.2.0', 'items': items, 'shared_file_queues': queues or []}))
        if not omit_registry:
            children = children if children is not None else []
            registry = Path(temp) / 'children' / 'registry.json'
            registry.parent.mkdir()
            for row in children:
                if isinstance(row, dict) and isinstance(row.get('key'), str):
                    deps = (mirror_deps or {}).get(row['key'], row.get('deps', []))
                    all_numbers = {r['key']: r['number'] for r in items + children if isinstance(r, dict) and isinstance(r.get('key'), str) and isinstance(r.get('number'), int)}
                    body = '## Direct prerequisites\n' + (mirror_lines or {}).get(row['key'], ', '.join(f'[{d} #{all_numbers.get(d, 999)}](https://github.com/Entif-AI/Bilqis-MLX/issues/{all_numbers.get(d, 999)})' for d in deps)) + '\n'
                    (registry.parent / (row['key'] + '.md')).write_text(body)
                    row['body_sha256'] = hashlib.sha256(body.encode()).hexdigest()
            registry.write_text(json.dumps({'schema': 'bilqis.bamf.all-child-registry/v1', 'entries': children}))
            issue_map = expected_map if expected_map is not None else {r['key']: r['number'] for r in items + children if isinstance(r, dict) and isinstance(r.get('key'), str) and isinstance(r.get('number'), int)}
            (Path(temp) / 'issue-map.json').write_text(json.dumps(issue_map))
        elif expected_map is not None:
            (Path(temp) / 'issue-map.json').write_text(json.dumps(expected_map))
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), str(path)],
                                text=True, capture_output=True)
        return result.returncode, json.loads(result.stdout)


class BamfWorkstackTest(unittest.TestCase):
    def test_valid_manifest_retains_dependency_and_one_writer_per_lane(self):
        code, report = run([item('A01', 'A', paths=['a.py']),
                            item('C01', 'C', ['A01'], ['c.py']),
                            item('B01', 'B', paths=['b.py'])])
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'valid')
        self.assertEqual(report['order'], ['A01', 'B01', 'C01'])
        self.assertEqual(report['issues'], [])
        self.assertEqual(report['schema'], 'bilqis.bamf.workstack.validation/v1')

    def test_malformed_input_is_a_reported_boundary_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            path.write_text('{')
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), str(path)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertEqual(report['status'], 'error')
            self.assertEqual(report['error']['code'], 'SCHOOL.BAMF_WORKSTACK.INPUT_INVALID')

    def test_cycle_and_missing_dependency_are_refused(self):
        for rows, expected in [([item('A01', 'A', ['C01']), item('C01', 'C', ['A01'])], 'DEPENDENCY_CYCLE'),
                               ([item('A01', 'A', ['C01'])], 'MISSING_DEPENDENCY')]:
            with self.subTest(expected=expected):
                code, report = run(rows)
                self.assertEqual(code, 1)
                self.assertEqual(report['status'], 'invalid')
                self.assertIn(expected, [issue['reason'] for issue in report['issues']])

    def test_cross_lane_shared_file_refused_even_with_new_suffix(self):
        code, report = run([item('A01', 'A', paths=['shared.py (new)']),
                            item('C01', 'C', paths=['shared.py'])])
        self.assertEqual(code, 1)
        self.assertIn({'code': 'SCHOOL.BAMF_WORKSTACK.VALIDATION_INVALID', 'reason': 'CROSS_LANE_FILE_OWNERSHIP', 'path': 'shared.py',
                       'lanes': ['A', 'C']}, report['issues'])

    def test_path_aliases_and_case_collisions_are_rejected(self):
        code, report = run([item('A01', 'A', paths=['pkg/x.py']),
                            item('C01', 'C', paths=['pkg/./x.py'])])
        self.assertEqual(code, 1)
        self.assertIn('FILE_PATH_INVALID', [issue['reason'] for issue in report['issues']])
        code, report = run([item('A01', 'A', paths=['Pkg/X.py']),
                            item('C01', 'C', paths=['pkg/x.py'])])
        self.assertEqual(code, 1)
        self.assertIn('CROSS_LANE_FILE_OWNERSHIP', [issue['reason'] for issue in report['issues']])

    def test_directory_claim_conflicts_with_another_lanes_file(self):
        code, report = run([item('A01', 'A', paths=['pkg/']),
                            item('C01', 'C', paths=['pkg/x.py'])])
        self.assertEqual(code, 1)
        self.assertIn('CROSS_LANE_FILE_OWNERSHIP', [issue['reason'] for issue in report['issues']])

    def test_directory_claim_without_trailing_slash_is_still_scoped(self):
        code, report = run([item('A01', 'A', paths=['pkg']),
                            item('C01', 'C', paths=['pkg/x.py'])])
        self.assertEqual(code, 1)
        self.assertIn('CROSS_LANE_FILE_OWNERSHIP', [issue['reason'] for issue in report['issues']])

    def test_declared_children_require_complete_registry(self):
        owner = item('C01', 'C')
        owner['children'] = ['C01.1', 'C01.2']
        code, report = run([owner], omit_registry=True)
        self.assertEqual(code, 1)
        self.assertIn('REGISTRY_REQUIRED', [issue['reason'] for issue in report['issues']])
        children = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': []}]
        code, report = run([owner], children)
        self.assertEqual(code, 1)
        self.assertIn('DECLARED_CHILDREN_MISMATCH', [issue['reason'] for issue in report['issues']])

    def test_child_cycle_in_combined_graph_is_rejected(self):
        children = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': ['C01.2']},
                    {'key': 'C01.2', 'number': 487, 'parent_key': 'C01', 'parent_number': 347, 'deps': ['C01.1']}]
        code, report = run([item('C01', 'C')], children)
        self.assertEqual(code, 1)
        self.assertIn('DEPENDENCY_CYCLE', [issue['reason'] for issue in report['issues']])

    def test_child_missing_dependency_and_parent_cycle_are_rejected(self):
        missing = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': ['C01.9']}]
        code, report = run([item('C01', 'C')], missing)
        self.assertEqual(code, 1)
        self.assertIn('MISSING_DEPENDENCY', [issue['reason'] for issue in report['issues']])
        parents = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01.2', 'parent_number': 487, 'deps': []},
                   {'key': 'C01.2', 'number': 487, 'parent_key': 'C01.1', 'parent_number': 486, 'deps': []}]
        code, report = run([item('C01', 'C')], parents)
        self.assertEqual(code, 1)
        self.assertIn('PARENT_CYCLE', [issue['reason'] for issue in report['issues']])

    def test_independent_issue_map_detects_nested_child_omission(self):
        owner = item('C01', 'C')
        owner['children'] = ['C01.1']
        child = {'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': []}
        code, report = run([owner], [child], {'C01': 347, 'C01.1': 486, 'C01.1a': 488})
        self.assertEqual(code, 1)
        self.assertIn('ISSUE_MAP_MISMATCH', [i['reason'] for i in report['issues']])

    def test_issue_map_detects_missing_registry_without_child_declarations(self):
        code, report = run([item('C01', 'C')], expected_map={'C01': 347, 'C01.1': 486}, omit_registry=True)
        self.assertEqual(code, 1)
        self.assertIn('ISSUE_MAP_MISMATCH', [i['reason'] for i in report['issues']])

    def test_unhashable_parent_is_typed_invalid_not_crash(self):
        child = {'key': 'C01.1', 'number': 486, 'parent_key': [], 'parent_number': 347, 'deps': []}
        code, report = run([item('C01', 'C')], [child])
        self.assertEqual(code, 1)
        self.assertIn('REGISTRY_ITEM_INVALID', [i['reason'] for i in report['issues']])
        self.assertTrue(all(i['code'] == 'SCHOOL.BAMF_WORKSTACK.VALIDATION_INVALID' for i in report['issues']))

    def test_reassigned_nested_child_is_rejected(self):
        owners = [item('A01', 'A'), item('C01', 'C')]
        children = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': []},
                    {'key': 'C01.1a', 'number': 488, 'parent_key': 'A01', 'parent_number': 345, 'deps': []}]
        code, report = run(owners, children)
        self.assertEqual(code, 1)
        self.assertIn('REGISTRY_PARENT_INVALID', [i['reason'] for i in report['issues']])

    def test_missing_registry_and_map_never_claim_complete_validation(self):
        code, report = run([item('C01', 'C')], omit_registry=True)
        self.assertEqual(code, 1)
        self.assertEqual({i['reason'] for i in report['issues']}, {'REGISTRY_REQUIRED', 'ISSUE_MAP_REQUIRED'})

    def test_non_mapping_issue_map_is_invalid(self):
        code, report = run([item('C01', 'C')], expected_map=[])
        self.assertEqual(code, 1)
        self.assertIn('ISSUE_MAP_INVALID', [i['reason'] for i in report['issues']])

    def test_repository_root_claim_cannot_hide_cross_lane_ownership(self):
        code, report = run([item('A01', 'A', paths=['.']), item('C01', 'C', paths=['pkg/x.py'])])
        self.assertEqual(code, 1)
        self.assertIn('FILE_PATH_INVALID', [i['reason'] for i in report['issues']])

    def test_missing_file_uses_typed_catalog_boundary(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '/nonexistent/bamf-manifest.json'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'SCHOOL.BAMF_WORKSTACK.INPUT_INVALID')

    def test_symbol_qualified_claims_require_one_explicit_writer(self):
        rows = [item('B01', 'B', paths=['shared.py:_train_step']), item('C01', 'C', paths=['shared.py:_make_batch/_train_step'])]
        code, report = run(rows)
        self.assertEqual(code, 1)
        self.assertIn('CROSS_LANE_FILE_OWNERSHIP', [i['reason'] for i in report['issues']])
        queue = {'path': 'shared.py', 'writer_lane': 'C', 'participants': ['B01', 'C01'], 'proposal_lanes': ['B']}
        code, report = run(rows, queues=[queue])
        self.assertEqual(code, 0)
        queue['participants'] = ['B01']
        code, report = run(rows, queues=[queue])
        self.assertEqual(code, 1)
        self.assertIn('SHARED_FILE_QUEUE_INVALID', [i['reason'] for i in report['issues']])

    def test_trainer_queue_rejects_wrong_or_malformed_writer(self):
        path = 'bilqis_mlx/learning/student_ops.py'
        rows = [item('B01', 'B', paths=[path]), item('C01', 'C', paths=[path])]
        for writer, proposals in [('B', ['C']), (['C'], ['B'])]:
            with self.subTest(writer=writer):
                queue = {'path': path, 'writer_lane': writer, 'participants': ['B01', 'C01'], 'proposal_lanes': proposals}
                code, report = run(rows, queues=[queue])
                self.assertEqual(code, 1)
                self.assertIn('SHARED_FILE_QUEUE_INVALID', [i['reason'] for i in report['issues']])

    def test_case_alias_cannot_change_trainer_owner(self):
        path = 'bilqis_mlx/learning/Student_ops.py'
        rows = [item('B01', 'B', paths=[path]), item('C01', 'C', paths=[path])]
        queue = {'path': path, 'writer_lane': 'B', 'participants': ['B01', 'C01'], 'proposal_lanes': ['C']}
        code, report = run(rows, queues=[queue])
        self.assertEqual(code, 1)
        self.assertIn('SHARED_FILE_QUEUE_INVALID', [i['reason'] for i in report['issues']])

    def test_blank_line_cannot_hide_direct_prerequisite(self):
        children = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': []},
                    {'key': 'C01.2', 'number': 487, 'parent_key': 'C01', 'parent_number': 347, 'deps': []}]
        line = '\n[C01.1 #486](https://github.com/Entif-AI/Bilqis-MLX/issues/486)'
        code, report = run([item('C01', 'C')], children, mirror_lines={'C01.2': line})
        self.assertEqual(code, 1)
        self.assertIn('MIRROR_DEPENDENCIES_MISMATCH', [i['reason'] for i in report['issues']])

    def test_checkpoint_proposal_requires_c_owned_queue(self):
        path = 'bilqis_mlx/runtime/checkpoints.py'
        rows = [item('B13', 'B', paths=[path + ':_advance'])]
        code, report = run(rows)
        self.assertEqual(code, 1)
        self.assertIn('SHARED_FILE_QUEUE_REQUIRED', [i['reason'] for i in report['issues']])
        queue = {'path': path, 'writer_lane': 'C', 'participants': ['B13'], 'proposal_lanes': ['B']}
        code, report = run(rows, queues=[queue])
        self.assertEqual(code, 0)

    def test_unknown_link_label_cannot_hide_direct_prerequisite(self):
        children = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': []},
                    {'key': 'C01.2', 'number': 487, 'parent_key': 'C01', 'parent_number': 347, 'deps': []}]
        line = '[C01.1](https://github.com/Entif-AI/Bilqis-MLX/issues/486)'
        code, report = run([item('C01', 'C')], children, mirror_lines={'C01.2': line})
        self.assertEqual(code, 1)
        self.assertIn('MIRROR_DEPENDENCIES_MISMATCH', [i['reason'] for i in report['issues']])

    def test_child_dependencies_match_hashed_mirror(self):
        children = [{'key': 'C01.1', 'number': 486, 'parent_key': 'C01', 'parent_number': 347, 'deps': []},
                    {'key': 'C01.2', 'number': 487, 'parent_key': 'C01', 'parent_number': 347, 'deps': []}]
        code, report = run([item('C01', 'C')], children, mirror_deps={'C01.2': ['C01.1']})
        self.assertEqual(code, 1)
        self.assertIn('MIRROR_DEPENDENCIES_MISMATCH', [i['reason'] for i in report['issues']])

    def test_same_lane_shared_file_does_not_create_a_second_writer(self):
        code, report = run([item('A01', 'A', paths=['shared.py']),
                            item('A02', 'A', paths=['shared.py'])])
        self.assertEqual(code, 0)
        self.assertEqual(report['issues'], [])
