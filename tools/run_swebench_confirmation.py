"""Run both predeclared confirmation repetitions after validation selection.

Every phase gets a fresh interpreter/household. No retries, replacement tasks,
model outcomes reused, APIs, training, publication or release operations.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


def command(module, *args):
    subprocess.run([sys.executable, '-m', module, *map(str, args)], check=True)


def require_completed(root):
    # The execution CLI can exit normally after retaining a stopped campaign.
    # A zero process exit alone must never authorize reporting/next inference.
    if json.loads((Path(root) / 'results.json').read_text()).get('status') != 'completed':
        raise RuntimeError('campaign not completed; retain its stop without proceeding')


def validate_selection(receipt):
    if receipt.get('format') != 'atmem-validation-profile-selection-v1' or receipt.get('confirmation_scores_consulted') is not False:
        raise ValueError('validation-only selection receipt required')
    chosen = receipt['selected']
    if chosen not in receipt['candidates']:
        raise ValueError('selected profile missing from retained candidates')
    from benchmarks.code_replay.swebench_selection import score, rank
    scored = []
    for candidate in receipt['candidates']:
        root = Path(candidate['campaign'])
        manifest, result = (root / 'manifest.json').read_bytes(), (root / 'results.json').read_bytes()
        if sha256(manifest).hexdigest() != candidate['manifest_sha256'] or sha256(result).hexdigest() != candidate['results_sha256']:
            raise ValueError('validation source changed after selection')
        parsed_manifest = json.loads(manifest)
        if score(parsed_manifest, json.loads(result)) != candidate['score']:
            raise ValueError('selection score differs from complete validation')
        if (parsed_manifest['product_runtime'] != candidate['product_runtime']
                or parsed_manifest['context_delivery'] != candidate['context_delivery']
                or parsed_manifest.get('model_graph_tools', True) != candidate['model_graph_tools']):
            raise ValueError('selected runtime or delivery differs from validation')
        scored.append(candidate)
    if chosen != min(scored, key=lambda candidate: rank(candidate['score'])):
        raise ValueError('profile does not follow the predeclared selection rule')
    return chosen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--cognee-runtime', type=Path, required=True)
    parser.add_argument('--root-prefix', type=Path, required=True)
    args = parser.parse_args()
    selection_raw = args.selection.read_bytes()
    chosen = validate_selection(json.loads(selection_raw))
    runtime_file = args.root_prefix.with_name(args.root_prefix.name + '-runtime.json')
    with runtime_file.open('x') as stream:
        json.dump(chosen['product_runtime'], stream, indent=2)
    roots = [args.root_prefix.with_name(args.root_prefix.name + '-r' + str(repeat)) for repeat in (1, 2)]
    # Freeze BOTH task schedules and orders before the first confirmation model.
    for repeat, root in enumerate(roots, 1):
        command('benchmarks.code_replay.swebench_pilot', 'prepare', '--root', root,
            '--product-runtime', runtime_file, '--cognee-runtime', args.cognee_runtime,
            '--cohort', 'confirmation', '--repetition', repeat, '--context-delivery', chosen['context_delivery'])
        capture = '''import os,json,sys
from pathlib import Path
from benchmarks.code_replay.swebench_pilot import vault
root=Path(sys.argv[1]);os.environ['ATMEM_HOME']=str(root/'home');service,principal=vault(root)
service.capture(run_id='pilot',kind='campaign.validation_selection',principal=principal,payload=json.load(sys.stdin))
'''
        subprocess.run([sys.executable, '-c', capture, str(root)], check=True, text=True,
            input=json.dumps({'selection': json.loads(selection_raw), 'selection_sha256': sha256(selection_raw).hexdigest(),
                             'orchestrator_source': Path(__file__).read_text(),
                             'confirmation_inference_started': False}))
    for repeat, root in enumerate(roots, 1):
        if repeat == 2:
            reuse = '''import sys,json
from benchmarks.code_replay.swebench_qualification_cache import reuse
print(json.dumps({'eligibility_proofs_reused':reuse(sys.argv[1],sys.argv[2]),'model_outcomes_reused':False}))
'''
            subprocess.run([sys.executable, '-c', reuse, str(roots[0]), str(root)], check=True)
        print(json.dumps({'repeat': repeat, 'phase': 'confirmation_execution', 'root': str(root)}), flush=True)
        # The trusted controller retains unavailable cells and never reruns a
        # started model. Nonzero exit stops orchestration, not silent recovery.
        command('benchmarks.code_replay.swebench_pilot', 'execute', '--root', root, '--count', 5)
        require_completed(root)
        command('benchmarks.code_replay.swebench_report', '--root', root)
        command('benchmarks.code_replay.swebench_timing', '--root', root)
        command('tools.capture_cognee_preparation_logs', '--root', root)
        command('tools.archive_swebench_campaign', '--root', root)
    print(json.dumps({'status': 'completed', 'repetitions': 2, 'roots': list(map(str, roots)),
                      'positive_outcome_asserted': False}), flush=True)


if __name__ == '__main__':
    main()
