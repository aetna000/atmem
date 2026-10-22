"""Post-run source-fragment audit; descriptive, never an acceptance metric.

Any overlap with an annotated turn is weaker than a complete utterance. This
tool checks that distinction after product outputs are frozen; it does not add
context or send source annotations to a retriever.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.dolphinbench.driver import AtMemHost
from .qualify import expand_reference


def covered_bytes(spans: list[tuple[int,int]]) -> int:
    total,end = 0,0
    for start,stop in sorted(spans):
        if type(start) is not int or type(stop) is not int or not 0 <= start <= stop:
            raise ValueError('invalid source offsets')
        total += max(0,stop-max(start,end))
        end=max(end,stop)
    return total


def audit(condition: Path, source: Path) -> dict:
    manifest=json.loads((condition/'manifest.json').read_text())
    if source.name!='Chat_1_Emi_Elise.json':
        raise ValueError('inspected development conversation only')
    data=json.loads(source.read_text())
    origin=Path(manifest.get('reused_frozen_history') or condition)
    host=AtMemHost(origin/'host','realtalk-development',memory_engine='context-v3')
    try:
        original=json.loads((origin/'checkpoint.json').read_text())
        current=host.service._canonical_checkpoint(host.service._load(host.binding['binding_id']))
        old=original['canonical']['context_engine']
        now=current['context_engine']
        # Legacy experiments predate semantic-table checkpoint coverage. Check
        # EVERY originally committed table and scope unchanged, without rewriting
        # that checkpoint or claiming the missing metadata was authenticated.
        if old['scope'] != now['scope'] or any(now['tables'].get(k)!=v for k,v in old['tables'].items()):
            raise ValueError('original canonical/source checkpoint mismatch')
        source_to_turn={}
        for observation in json.loads((origin/'ingestion.json').read_text()):
            for span in observation['receipt'].get('formation',{}).get('represented_ranges',[]):
                source_to_turn[span['source_id']]=observation['turn_id']
        binding=host.service._binding(host.service._load(host.binding['binding_id']))
        rows=[]
        with binding.v3().memory() as (memory,scope):
            gen=memory.context_generation(scope)['generation_id']
            lengths={r['source_id']:int(r['n']) for r in memory.store._conn.execute(
                'SELECT source_id,SUM(length(content_bytes)) n FROM context_source_parts GROUP BY source_id')}
            for qid in manifest['selected_qa_indices']:
                ruling=json.loads((condition/f'question-{qid}.json').read_text())
                selected=ruling.get('candidate_ids',[]) if ruling.get('reason')=='authorized' else []
                intervals={}
                for identity in selected:
                    for span in memory.store._conn.execute('''SELECT r.source_id,r.start_offset,r.end_offset
                        FROM context_unit_ranges u JOIN context_source_ranges r USING(range_id)
                        WHERE u.generation_id=? AND u.unit_id=?''',(gen,identity)):
                        intervals.setdefault(span['source_id'],[]).append((span['start_offset'],span['end_offset']))
                reached={source_to_turn[sid] for sid in intervals}
                # This source has one text part per observation. Gaps between
                # sentence ranges can be whitespace: classify as almost-complete
                # separately, do not claim an exact full byte reconstruction.
                complete={source_to_turn[sid] for sid,spans in intervals.items()
                          if covered_bytes(spans)==lengths[sid]}
                expected={r for raw in data['qa'][qid]['evidence'] for r in expand_reference(raw)}
                rows.append({'qa_index':qid,'annotated_turns':len(expected),
                    'annotated_turns_with_any_fragment':len(expected&reached),
                    'annotated_turns_with_all_original_bytes':len(expected&complete),
                    'all_annotated_turns_have_any_fragment':expected.issubset(reached),
                    'all_annotated_turns_have_all_original_bytes':expected.issubset(complete),
                    'selected_units':len(selected),'distinct_source_turns':len(reached)})
        return {'mode':'posthoc-source-fragment-audit-not-task-quality',
                'condition':condition.name,'questions':len(rows),'rows':rows,
                'cases_all_annotated_turns_any_fragment':sum(r['all_annotated_turns_have_any_fragment'] for r in rows),
                'cases_all_annotated_turns_all_bytes':sum(r['all_annotated_turns_have_all_original_bytes'] for r in rows),
                'legacy_checkpoint_original_tables_verified':True,
                'legacy_semantic_metadata_coverage_not_retroactively_claimed':True,
                'single_source_part_per_observation':True,'paid_api_usd':0,'ready_for_600':False}
    finally:
        host.stop()


def main():
    from benchmarks.dolphinbench.gateway import save_new
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('condition','source','output'):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    report=audit(args.condition,args.source)
    save_new(args.output,report)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__=='__main__':
    main()
