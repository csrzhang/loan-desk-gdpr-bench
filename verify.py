"""Replay frozen results and verify source attribution. Requires Python 3.9+."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from evidence import check_reference, source_lines

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / 'reference'
FILES = ('app.py', 'store.py', 'style.css', 'views.py')
TARGET = {
    'enqueue-only-consent': 'GDPR04',
    'acknowledge-only-correction': 'GDPR07',
    'score-during-restriction': 'GDPR09',
    'omit-portable-term': 'GDPR10',
    'record-only-reversal': 'GDPR13',
}

def load(path):
    return json.loads(path.read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(condition, reason):
    if not condition:
        raise ValueError(reason)

def observe(project):
    command = [sys.executable, '-B', str(ROOT / 'validation/observe.py'), str(project)]
    return json.loads(subprocess.check_output(command, timeout=120))

def changed(run):
    return {key for key, value in run.items() if value['contract'] == 'FAIL'}

def apply_patch(project, op):
    patch = REFERENCE / 'operators' / (op + '.patch')
    subprocess.run(['patch', '-s', '-F', '0', '-p1', '-i', str(patch)],
                   cwd=project, check=True, stdin=subprocess.DEVNULL, timeout=20)

def verify():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operators', action='store_true', help='Also run all five isolated mutations and rebuild each compound.')
    args = parser.parse_args()
    manifest = load(REFERENCE / 'manifest.json')
    check(digest(ROOT/'scope.json') == manifest['scope_sha256'], 'Scope changed')
    ids = [f'GDPR{i:02}' for i in range(1,14)]
    scope = load(ROOT/'scope.json')['obligations']
    check([row['obligation_id'] for row in scope] == ids, 'Scope inventory differs')
    for file, expected in manifest['validation'].items():
        check(digest(ROOT/'validation'/file) == expected, f'Changed validation helper {file}')
    for name, item in manifest['projects'].items():
        project = ROOT / 'projects' / name
        hashes = {file:digest(project/file) for file in FILES}
        snapshot = hashlib.sha256(''.join(f'{value}  {key}\n' for key,value in sorted(hashes.items())).encode()).hexdigest()
        audit = load(REFERENCE/name/'audit.json')
        check(hashes == item['files'] and snapshot == item['source_sha256'] == audit['source_sha256'], f'{name}: snapshot changed')
        check(audit['project'] == name and [x['obligation_id'] for x in audit['records']] == ids, f'{name}: incomplete audit')
        received = observe(project)
        stored = load(REFERENCE/name/'run.json')
        check(set(received) == set(ids), f'{name}: incomplete run')
        check(changed(received) == {TARGET[k] for k in item['operators']}, f'{name}: unexpected failures')
        sources = source_lines(project)
        for spec, row in zip(scope, audit['records']):
            oid = spec['obligation_id']
            check(all(row[k] == spec[k] for k in ('article','scenario','title')), f'{name}/{oid}: scope mismatch')
            check(row['runtime_evidence'] == stored[oid], f'{name}/{oid}: receipt mismatch')
            # Traceback formatting can vary between Python versions.
            for field in ('test','contract','observed'):
                check(received[oid][field] == stored[oid][field], f'{name}/{oid}: changed {field}')
            verdict = 'CONTRADICTED' if oid in changed(received) else 'SUPPORTED'
            check(verdict == row['verdict'] and row['evidence'] and row['explanation'], f'{name}/{oid}: reference mismatch')
            check_reference(row, sources)
            for e in row['evidence']:
                check(e['path'] in FILES, 'Unexpected source file')
                lines = (project/e['path']).read_text().splitlines()
                a,b = e['start_line'], e['end_line']
                check(1 <= a <= b <= len(lines) and '\n'.join(lines[a-1:b]) == e['quote'], f'{name}/{oid}: bad source span')
        print(f"{name}: 13 references reproduced; contradicted: {', '.join(sorted(changed(received))) or 'none'}")
    if args.operators:
        base = ROOT / 'projects/base'
        for label, ops in [(op,[op]) for op in TARGET] + [(name,m['operators']) for name,m in manifest['projects'].items() if m['operators']]:
            with tempfile.TemporaryDirectory() as directory:
                temp = Path(directory)
                for file in FILES:
                    shutil.copyfile(base/file,temp/file)
                for op in ops:
                    apply_patch(temp,op)
                if label in TARGET:
                    defects=changed(observe(temp))
                    check(defects == {TARGET[label]}, f'{label}: unexpected single-operator result')
                    print(f'{label} alone: 12 pass, 1 contradicted ({TARGET[label]})')
                else:
                    check(digest(temp/'store.py') == manifest['projects'][label]['files']['store.py'], f'{label}: composition mismatch')
                    print(f'{label}: patched source reproduced byte for byte')

if __name__=='__main__':
    verify()
