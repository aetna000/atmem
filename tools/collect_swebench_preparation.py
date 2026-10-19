"""Collect latest preparation receipts, never select the best coding outcome."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay.swebench_pilot import remote

PROGRAM = '''import pathlib,json,hashlib,shutil
root=pathlib.Path('/home/user/atmem-swebench-20261019')
states={'sympy':root/'large-repo-fix/sympy-cached',
        **{name:root/'index-fix-qualification-v2'/name for name in ('sphinx','matplotlib','django','scikit-learn')}}
rows=[]
for name,state in states.items():
 reports=list(state.glob('summary*.json'))
 if not reports:rows.append({'repository':name,'status':'missing'});continue
 p=max(reports,key=lambda p:p.stat().st_mtime)
 raw=p.read_bytes();d=json.loads(raw)
 mode='existing_generation_revalidation' if d.get('index',{}).get('status')=='unchanged' else d.get('extraction_mode','unspecified')
 rows.append({'repository':name,'status':d['status'],'receipt_path':str(p),'receipt_sha256':hashlib.sha256(raw).hexdigest(),
  'source_files':d.get('source_files'),'writer_facts':d.get('facts'),'extraction_mode':mode,'snapshot_id':d.get('index',{}).get('snapshot_id'),
  'context_bytes':d.get('context',{}).get('bytes'),'mcp':d.get('mcp'),'error':d.get('error')})
runtime=json.loads((root/'candidate-bounded-graph-20261019/runtime.json').read_text())
print(json.dumps({'candidate_runtime':runtime,'atmem_preparation':rows,'windows_free_gib':shutil.disk_usage('/mnt/c').free/1024**3}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    response = remote(PROGRAM, timeout=30)
    if response.returncode:
        raise RuntimeError('preparation receipt collection failed')
    result = json.loads(response.stdout)
    base = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks')
    baseline = base / 'swebench-lite-official-runtime-20261019'
    result['original_pilot'] = json.loads((baseline / 'comparison.json').read_text())
    result['original_results_sha256'] = sha256((baseline / 'results.json').read_bytes()).hexdigest()
    state = base / 'cognee-swebench-source-20261019/cognee-state'
    p = max(state.glob('summary*.json'), key=lambda p: p.stat().st_mtime)
    result['cognee_preparation'] = json.loads(p.read_text())
    result['cognee_preparation']['receipt_path'] = str(p)
    result['cognee_preparation']['receipt_sha256'] = sha256(p.read_bytes()).hexdigest()
    audit = '''import importlib.metadata as m,pathlib,hashlib,json,subprocess
root=pathlib.Path('/tmp/atmem-code-research.yKNuul/cognee')
source=root/'cognee';installed=pathlib.Path(m.distribution('cognee').locate_file('cognee'))
files=list(source.rglob('*.py'));bad=[str(p.relative_to(source)) for p in files if not (installed/p.relative_to(source)).is_file() or hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((installed/p.relative_to(source)).read_bytes()).digest()]
print(json.dumps({'commit':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'source_dirty':bool(subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True)),'version':m.version('cognee'),'matched_python_files':len(files)-len(bad),'mismatched_python_files':len(bad)}))'''
    result['cognee_source_audit'] = json.loads(subprocess.check_output([
        '/private/tmp/atmem-click-cognee-upstream-20261018/bin/python', '-I', '-c', audit], text=True))
    result['interpretation'] = ('Preparation checks only; no new solver outcomes. AtMem runs on Windows/WSL and '
        'Cognee preparation on Mac; their load/query times are not a controlled head-to-head comparison. '
        'Original pilot outcomes unchanged. Cold indexing is not inferred from cached artifact or unchanged-generation rechecks.')
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({'atmem_passed': sum(r['status'] == 'passed' for r in result['atmem_preparation']),
                      'cognee_preparation': result['cognee_preparation']['status'],
                      'windows_free_gib': result['windows_free_gib'], 'output': str(args.output)}), flush=True)


if __name__ == '__main__':
    main()
