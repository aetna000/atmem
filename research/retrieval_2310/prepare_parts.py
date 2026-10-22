"""Prepare local encrypted semantic derivatives from frozen source history only."""
import argparse
import json
from pathlib import Path

from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.part_semantic import SourcePartSemanticIndex
from atmem.context_engine.service import stored_manifest
from atmem.semantic.providers import OllamaEmbedder
from benchmarks.dolphinbench.driver import AtMemHost
from benchmarks.dolphinbench.gateway import save_new


def prepare(baseline: Path,output: Path):
    model=OllamaEmbedder('nomic-embed-text:latest',
        model_version='sha256:0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f',
        truncate=False)
    output.mkdir(parents=True,exist_ok=True)
    for persona in ('alex','morgan','riley'):
        if (output/(persona+'-ready.json')).exists():
            raise ValueError('completed derivative exists; do not regenerate it')
        host=AtMemHost(baseline/'memory',persona,memory_engine='context-v3')
        try:
            checkpoint=json.loads((baseline/'checkpoints'/f'{persona}.json').read_text())
            host.verify_checkpoint(checkpoint)
            binding=host.service._binding(host.service._load(host.binding['binding_id']))
            with binding.v3().memory() as (memory,scope):
                gen=memory.context_generation(scope)
                request=ContextRequestV3(context_id='local-index-build',request_id='local-index-build',
                    query='local source index construction',scope=scope,profile_id='context-fast',
                    mode='active',generation=gen['canonical_generation'],turn_id='index-build')
                manifest=stored_manifest(memory.store,request,generation_id=gen['generation_id'])
                index=SourcePartSemanticIndex(memory.store,generation_id=gen['generation_id'],
                    manifest=manifest,path=output/(gen['generation_id']+'.db'),model_identity=model.identity)
                try:
                    result=index.build(model,progress=lambda count:print(json.dumps({
                        'persona':persona,'embedded_chunks':count,'primary_model_calls':0}),flush=True))
                finally: index.close()
            host.verify_checkpoint(checkpoint)
            save_new(output/(persona+'-ready.json'),{**result,'persona':persona,
                'original_checkpoint_verified_before_and_after':True,'paid_api_usd':0})
            print(json.dumps({'persona':persona,'index_ready':True,'vectors':result['vectors']}),flush=True)
        finally: host.stop()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    prepare(args.baseline,args.output)


if __name__=='__main__':main()
