"""Read-only postflight for all BAMF issue mirrors and native child edges."""
import concurrent.futures
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

TASKS=Path(__file__).resolve().parents[3]/'docs/tasks/bamf-0.2'
REPO='repos/Entif-AI/Bilqis-MLX'

def gh(path):
    p=subprocess.run(['gh','api',path],text=True,capture_output=True,check=True)
    return json.loads(p.stdout)

def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()

def issue_body_matches(local, remote):
    """Accept equal content with at most one terminal LF of GitHub transport drift."""
    if local.rstrip('\n') != remote.rstrip('\n'):
        return False
    local_lf=len(local)-len(local.rstrip('\n'))
    remote_lf=len(remote)-len(remote.rstrip('\n'))
    return abs(local_lf-remote_lf) <= 1

def main():
    owners=json.loads((TASKS/'workstack.json').read_text())['items']
    children=json.loads((TASKS/'children/registry.json').read_text())['entries']
    supplement=json.loads((TASKS/'native-hierarchy-supplement.json').read_text())['entries']
    records=[(x['key'],x['number'],x['body_sha256'],TASKS/'issues'/f"{x['key']}.md") for x in owners]
    records += [(x['key'],x['number'],x['body_sha256'],TASKS/'children'/f"{x['key']}.md") for x in children]
    def check_body(record):
        key,num,sha,path=record
        body=path.read_text()
        remote=gh(f'{REPO}/issues/{num}')
        if digest(body)!=sha or not issue_body_matches(body, remote.get('body') or ''):
            return f'{key} #{num}: local/registry/live issue body mismatch'
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        failures=[v for v in pool.map(check_body,records) if v]
    hierarchy=defaultdict(set)
    for c in children:hierarchy[c['parent_number']].add(c['number'])
    for row in supplement:hierarchy[row['parent_number']].add(row['child_number'])

    expected_hierarchy={(parent,child) for parent,numbers in hierarchy.items() for child in numbers}
    def check_links(pair):
        parent,numbers=pair
        actual={v['number'] for v in gh(f'{REPO}/issues/{parent}/sub_issues')}
        if actual!=numbers:return f'{parent}: expected {sorted(numbers)}, got {sorted(actual)}'
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        failures += [v for v in pool.map(check_links,sorted(hierarchy.items())) if v]

    for row in supplement:
        remote=gh(f"{REPO}/issues/{row['child_number']}")
        body=(remote.get('body') or '').rstrip('\n')
        if digest(body)!=row['child_body_content_sha256']:
            failures.append(f"supplement child #{row['child_number']}: body-content digest mismatch")
        if remote.get('title')!=row['child_title'] or remote.get('state','').upper()!=row['child_state']:
            failures.append(f"supplement child #{row['child_number']}: title/state mismatch")
    # Native parent/child relationships are validated above against GitHub's
    # sub-issue API. They are hierarchy edges, not prerequisite edges, and must
    # not participate in dependency cycle detection.
    edges={i['key']:list(i['deps']) for i in owners}
    for c in children:edges[c['key']]=list(c['deps'])
    done=set(); active=set()
    def visit(key):
        if key in active:failures.append(f'dependency cycle at {key}');return
        if key in done:return
        active.add(key)
        for dep in edges[key]:
            if dep not in edges:failures.append(f'{key}: unknown dependency {dep}')
            else:visit(dep)
        active.remove(key);done.add(key)
    for k in edges:visit(k)
    if failures:
        for error in failures:print('FAIL:',error)
        raise SystemExit(1)
    print(f'PASS: {len(owners)} original full issue bodies and {len(children)} child bodies match live GitHub content with <=1 terminal-LF transport delta')
    print(f'PASS: frozen planning hierarchy plus audited supplement: {len(expected_hierarchy)} native edges across {len(hierarchy)} expected parent groups')
    print(f'PASS: frozen dependency DAG {len(edges)} nodes verified independently of native hierarchy')
    print('NOTE: this checks publication only; no model or trainer execution')

if __name__=='__main__':main()
