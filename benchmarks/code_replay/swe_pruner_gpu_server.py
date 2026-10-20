"""Unmodified upstream SWE-Pruner inference behind a bounded private SSH pipe."""
import argparse
from contextlib import redirect_stdout
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

REVISION = '863cee3198c715c9df1faa422a3490e0832bb734'
BACKBONE = 'e61197ed45024b0ed8a2d74b80b4d909f1255473'
ROOT = Path('/workspace/atmem-swe-pruner')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args()
    output = sys.stdout
    os.environ['HF_HOME'] = str(ROOT / 'hf')
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    tick = time.monotonic()
    with redirect_stdout(sys.stderr):
        from huggingface_hub import snapshot_download
        path = snapshot_download('ayanami-kitasan/code-pruner', revision=REVISION,
                                 local_dir=str(ROOT / 'model'), token=False)
        base = snapshot_download('Qwen/Qwen3-Reranker-0.6B', revision=BACKBONE,
                                 local_dir=str(ROOT / 'backbone-config'), allow_patterns=['config.json'], token=False)
        import torch
        from swe_pruner.configuration import SwePrunerConfig
        from swe_pruner.prune_wrapper import SwePrunerForCodePruning, PruneRequest
        if not torch.cuda.is_available():
            raise RuntimeError('qualified CUDA device required; no silent CPU fallback')
        config = SwePrunerConfig.from_pretrained(path, local_files_only=True,
            backbone_model_name_or_path=base, trust_remote_code=False)
        model = SwePrunerForCodePruning.from_pretrained(path, config=config, local_files_only=True)
        torch.cuda.synchronize()
        attention = model.model.backbone.config._attn_implementation
        if attention != 'flash_attention_2':
            raise RuntimeError('FlashAttention-2 did not activate; do not score an unqualified backend')
    metadata = {'model_revision': REVISION, 'backbone_config_revision': BACKBONE,
                'gpu': torch.cuda.get_device_name(), 'torch': torch.__version__,
                'dtype': str(next(model.parameters()).dtype), 'attention': attention,
                'package': importlib.metadata.version('swe-pruner'),
                'flash_attention': importlib.metadata.version('flash-attn'),
                'transformers': importlib.metadata.version('transformers'),
                'load_seconds': time.monotonic() - tick,
                'adaptations': [], 'threshold': 0.5}
    (ROOT / 'last-runtime.json').write_text(json.dumps(metadata, indent=2))

    def prune(request):
        if set(request) != {'query', 'code'} or not all(isinstance(v, str) for v in request.values()):
            raise ValueError('exact textual query and code required')
        if not 1 <= len(request['query']) <= 1000 or not 1 <= len(request['code'].encode()) <= 24000:
            raise ValueError('bounded nonempty query and source required')
        tick = time.monotonic()
        with redirect_stdout(sys.stderr):
            result = model.prune(PruneRequest(**request, threshold=0.5))
            torch.cuda.synchronize()
        elapsed = time.monotonic() - tick
        raw = result.model_dump()
        if result.error_msg:
            raise RuntimeError(result.error_msg)
        with (ROOT / 'inference-audit.jsonl').open('a') as audit:
            audit.write(json.dumps({'request': request, 'result': raw, 'seconds': elapsed,
                                    'runtime': metadata}) + '\n')
        return {key: raw[key] for key in ('pruned_code', 'kept_frags', 'origin_token_cnt',
                                          'left_token_cnt', 'model_input_token_cnt', 'score')} | {
            'seconds': elapsed, 'source_sha256': sha256(request['code'].encode()).hexdigest()}

    if args.qualify:
        cases = json.loads((ROOT / 'cases.json').read_text())
        trials = []
        for case in cases['cases']:
            trial = {'id': case['id'], **prune({'query': case['query'], 'code': case['code']})}
            trials.append(trial)
            print(json.dumps({'stage': 'qualified_case', 'id': case['id'], 'seconds': trial['seconds'],
                              'original_tokens': trial['origin_token_cnt'], 'remaining_tokens': trial['left_token_cnt']}),
                  file=output, flush=True)
        (ROOT / 'qualification.json').write_text(json.dumps({'runtime': metadata, 'cases': trials}, indent=2))
        return
    print(json.dumps({'status': 'ready', 'runtime': metadata}), file=output, flush=True)
    for line in sys.stdin:
        try:
            if len(line.encode()) > 50000:
                raise ValueError('request too large')
            response = prune(json.loads(line))
        except Exception as exc:
            response = {'error': type(exc).__name__ + ': ' + str(exc)}
        print(json.dumps(response), file=output, flush=True)


if __name__ == '__main__':
    main()
