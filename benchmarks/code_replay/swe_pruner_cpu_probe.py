"""Windows CPU feasibility probe for pinned SWE-Pruner weights.

Benchmark-only: trims masked right padding, never real code or query tokens.
Verifies scores against a padded reference before exercising real Click source.
Not shipped in AtMem, not a task-resolution or solver-token-saving result.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import time


def main(payload):
    root = Path('/home/user/atmem-swe-pruner-20261019')
    os.environ['HF_HOME'] = str(root / 'hf')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    import torch
    from swe_pruner.configuration import SwePrunerConfig
    import swe_pruner.prune_wrapper as wrapper
    torch.set_num_threads(4)
    config = SwePrunerConfig.from_pretrained(str(root / 'model'), local_files_only=True,
        backbone_model_name_or_path=str(root / 'backbone-config'), torch_dtype='float32', trust_remote_code=False)
    tick = time.monotonic()
    model = wrapper.SwePrunerForCodePruning.from_pretrained(str(root / 'model'), config=config,
        torch_dtype=torch.float32, local_files_only=True)
    load = time.monotonic() - tick
    original = wrapper.build_input_for_llm

    def unpadded(*args, **kwargs):
        batch = original(*args, **kwargs)
        mask = batch['attention_mask'][0]
        length = int(mask.sum().item())
        if not (mask[:length].eq(1).all() and mask[length:].eq(0).all()) or batch['doc_end'] > length:
            raise ValueError('only contiguous masked right padding may be removed')
        for key in ('input_ids', 'attention_mask'):
            batch[key] = batch[key][:, :length]
        return batch

    query = 'Find the function that returns a greeting'
    code = 'def greet(name):\n    return "Hello " + name\n\ndef add(a,b):\n    return a+b\n'
    tick = time.monotonic()
    reference = model._process_single_chunk(query, code, model.tokenizer, max_length=256)
    reference_seconds = time.monotonic() - tick
    wrapper.build_input_for_llm = unpadded
    tick = time.monotonic()
    trimmed = model._process_single_chunk(query, code, model.tokenizer, max_length=256)
    trimmed_seconds = time.monotonic() - tick
    if [x[0] for x in reference[1]] != [x[0] for x in trimmed[1]] or reference[2] != trimmed[2]:
        raise ValueError('padding optimization changed token identity or offsets')
    delta = max(abs(a[1] - b[1]) for a, b in zip(reference[1], trimmed[1]))
    diagnostics = {'max_token_score_difference': delta, 'document_score_difference': abs(reference[0] - trimmed[0]),
                   'reference_seconds': reference_seconds, 'trimmed_seconds': trimmed_seconds,
                   'threshold_flips': sum((a[1] >= 0.5) != (b[1] >= 0.5) for a, b in zip(reference[1], trimmed[1]))}
    (root / 'padding-equivalence.json').write_text(json.dumps(diagnostics, indent=2))
    print(json.dumps({'stage': 'padding_equivalence_measured', **diagnostics}), flush=True)
    if delta > 1e-4 or abs(reference[0] - trimmed[0]) > 1e-4:
        raise ValueError('padding optimization failed numerical equivalence check')
    print(json.dumps({'stage': 'padding_equivalence_passed', 'max_token_score_difference': delta,
                      'reference_seconds': reference_seconds, 'trimmed_seconds': trimmed_seconds}), flush=True)
    trials = []
    for case in payload['cases']:
        tick = time.monotonic()
        result = model.prune(wrapper.PruneRequest(query=case['query'], code=case['code'], threshold=0.5))
        trials.append({'id': case['id'], 'seconds': time.monotonic() - tick,
                       'source_sha256': sha256(case['code'].encode()).hexdigest(),
                       'response': result.model_dump()})
        print(json.dumps({'stage': 'case_completed', 'id': case['id'],
                          'seconds': trials[-1]['seconds'], 'original_tokens': result.origin_token_cnt,
                          'remaining_tokens': result.left_token_cnt}), flush=True)
    row = {'format': 'swe-pruner-cpu-feasibility-v1', 'model_revision': '863cee3198c715c9df1faa422a3490e0832bb734',
           'device': 'cpu', 'dtype': 'float32', 'attention': model.model.backbone.config._attn_implementation,
           'adaptation': 'masked-right-padding-removal; upstream weights, threshold and pruning logic unchanged',
           'load_seconds': load, 'reference_padded_positions': 256,
           'equivalence_max_token_score_difference': delta, 'cases': trials,
           'task_resolution': 'not_measured', 'agent_tokens': 'not_measured'}
    (root / 'cpu-feasibility.json').write_text(json.dumps(row, indent=2))
    print(json.dumps({'status': 'completed', 'cases': len(trials)}), flush=True)


if __name__ == '__main__':
    import sys
    main(json.loads(sys.stdin.read()))
