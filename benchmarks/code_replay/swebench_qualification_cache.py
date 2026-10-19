"""Reuse exact unchanged/reference eligibility proofs, never solver outcomes.

For a new campaign only: identical task bytes, upstream harness, image and all
trusted grading helpers are mandatory. Failed or missing eligibility is not
converted into a pass. Every reuse gets its own provenance event.
"""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path

from atmem.core.canonical import canonical_json
from benchmarks.code_replay.swebench_pilot import vault, validate_frozen_manifest

HELPERS = ('resolution_value', 'run', 'guard', 'start', 'stop', 'execute', 'reset',
           'grade', 'checked_name', 'name')


def grader_binding(source):
    tree = ast.parse(source)
    functions = {node.name: ast.dump(node, include_attributes=False) for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    constants = [ast.dump(node, include_attributes=False) for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id in {'ROOT', 'LABEL', 'PREFIX'} for target in node.targets)]
    imports = [ast.dump(node, include_attributes=False) for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    dispatch = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'dispatch')
    grade_branch = [ast.dump(node, include_attributes=False) for node in dispatch.body if isinstance(node, ast.If)
                    and ast.unparse(node.test) == "action == 'grade'"]
    if len(grade_branch) != 1:
        raise ValueError('exact trusted grade dispatch required')
    return sha256(canonical_json({'functions': {name: functions[name] for name in HELPERS},
                                  'constants': constants, 'imports': imports, 'grade_dispatch': grade_branch}).encode()).hexdigest()


def reuse(source_root, destination_root):
    source_root, destination_root = Path(source_root), Path(destination_root)
    if source_root.resolve() == destination_root.resolve():
        raise ValueError('eligibility reuse requires a new campaign')
    before = json.loads((source_root / 'manifest.json').read_text())
    after = json.loads((destination_root / 'manifest.json').read_text())
    if any(before[key] != after[key] for key in ('dataset', 'revision', 'parquet_sha256', 'harness_commit')):
        raise ValueError('dataset/harness identity differs')
    os.environ['ATMEM_HOME'] = str(source_root / 'home')
    original, original_principal = vault(source_root)
    locks = [e['envelope']['payload'] for e in original.inspect(original_principal, 'pilot')
             if e['envelope']['event_type'] in {'execution.locked', 'execution.continuation_locked'}]
    current = grader_binding(Path(__file__).with_name('swebench_worker.py').read_text())
    if not locks or any(grader_binding(lock['source_text']['swebench_worker.py']) != current for lock in locks):
        raise ValueError('trusted grading helpers changed')
    os.environ['ATMEM_HOME'] = str(destination_root / 'home')
    target, principal = vault(destination_root)
    pilot = target.inspect(principal, 'pilot')
    validate_frozen_manifest(pilot, after)
    if any(e['envelope']['event_type'].startswith('execution.') for e in pilot):
        raise ValueError('freeze reuse before destination execution starts')
    count = 0
    for row in after['selected']:
        identity = row['instance_id']
        incoming = target.inspect(principal, identity)
        if any(e['envelope']['event_type'].startswith('environment.') for e in incoming):
            raise ValueError('destination already has eligibility history')
        prior = original.inspect(original_principal, identity)
        old_tasks = [e['envelope']['payload'] for e in prior if e['envelope']['event_type'] == 'upstream.task']
        new_tasks = [e['envelope']['payload'] for e in incoming if e['envelope']['event_type'] == 'upstream.task']
        terminals = [e for e in prior if e['envelope']['event_type'] == 'environment.terminal']
        if len(old_tasks) != 1 or old_tasks != new_tasks:
            raise ValueError('full task bytes differ')
        if not terminals or not terminals[-1]['envelope']['payload'].get('qualified'):
            continue
        terminal = terminals[-1]
        controls = [e['envelope']['payload'] for e in prior if e['envelope']['event_type'] == 'environment.control']
        if not all(any(e['phase'] == phase for e in controls) for phase in ('unchanged', 'reference')):
            raise ValueError('original actual controls missing')
        provenance = {'source_campaign': source_root.name,
            'original_terminal_sha256': sha256(canonical_json(terminal).encode()).hexdigest(),
            'task_sha256': sha256(canonical_json(old_tasks[0]).encode()).hexdigest(),
            'grading_helpers_sha256': current, 'model_outcomes_reused': False}
        target.capture(run_id=identity, kind='environment.qualification_reused', principal=principal,
                       payload={**provenance, 'original_terminal': terminal, 'controls': controls})
        target.capture(run_id=identity, kind='environment.terminal', principal=principal,
                       payload={**terminal['envelope']['payload'], 'qualification_provenance': provenance})
        count += 1
    return count
