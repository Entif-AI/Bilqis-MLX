"""Read-only postflight for all BAMF issue mirrors and native child edges."""
import concurrent.futures
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

TASKS=Path(__file__).resolve().parents[1]/'docs/tasks/bamf-0.2'
REPO='repos/Entif-AI/Bilqis-MLX'

def gh(path):
    p=subprocess.run(['gh','api',path],text=True,capture_output=True,check=True)
    return json.loads(p.stdout)

def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()

def main():
    owners=json.loads((TASKS/'workstack.json').read_text())['items']
    children=json.loads((TASKS/'children/registry.json').read_text())['entries']
    records=[(x['key'],x['number'],x['body_sha256'],TASKS/'issues'/f"{x['key']}.md") for x in owners]
    records += [(x['key'],x['number'],x['body_sha256'],TASKS/'children'/f"{x['key']}.md") for x in children]
    def check_body(record):
        key,num,sha,path=record
        body=path.read_text()
        remote=gh(f'{REPO}/issues/{num}')
        if digest(body)!=sha or remote.get('body')!=body:
            return f'{key} #{num}: local/registry/live issue body mismatch'
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        failures=[v for v in pool.map(check_body,records) if v]
    hierarchy=defaultdict(set)
    for c in children:hierarchy[c['parent_number']].add(c['number'])
    def check_links(pair):
        parent,numbers=pair
        actual={v['number'] for v in gh(f'{REPO}/issues/{parent}/sub_issues')}
        if actual!=numbers:return f'{parent}: expected {sorted(numbers)}, got {sorted(actual)}'
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        failures += [v for v in pool.map(check_links,sorted(hierarchy.items())) if v]
    edges={i['key']:list(i['deps'])+list(i.get('children',[])) for i in owners}
    for c in children:edges[c['key']]=list(c['deps'])
    for c in children:
        if c['key'] not in edges[c['parent_key']]:edges[c['parent_key']].append(c['key'])
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
    print(f'PASS: {len(owners)} original full issue bodies and {len(children)} child bodies match live GitHub exactly')
    print(f'PASS: {len(hierarchy)} native parent-child groups and {len(edges)} DAG nodes verified')
    print('NOTE: this checks publication only; no model or trainer execution')

if __name__=='__main__':main()
