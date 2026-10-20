"""Prospective CD1 schedule and bounded reuse of the exercised staging driver."""
import ast
from hashlib import sha256
import inspect

RUN = 'external-windows-corrective-development-staging-v1-20261018'
SEED = 'atmem-corrective-development-screen-20261018-v1'


def development_blocks(original):
    identities = {b['instance_id'] for b in original}
    if len(original) != 38 or len(identities) != 19:
        raise ValueError('exact original nineteen-issue cohort required')
    for identity in identities:
        if sorted(b['repeat'] for b in original if b['instance_id'] == identity) != [1, 2]:
            raise ValueError('original repeated issue identity differs')
    ordered = sorted(identities, key=lambda i: sha256((SEED+'\0'+i).encode()).hexdigest())
    return [{'instance_id': identity, 'repeat': 1, 'slot': slot,
             'order': ['native', 'tools'] if slot % 2 == 0 else ['tools', 'native']}
            for slot, identity in enumerate(ordered)]


def staging_source(original):
    changes = {
        "RUN='external-windows-confirmation-v3-staging-v1-20261018'": 'RUN='+repr(RUN),
        "CASE_ROOT='/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v3'":
            "CASE_ROOT='/home/jt/atmem-benchmark-runtime-20261018/corrective-development-stage-v1'",
        "'external-windows-product-build-source-storage-v1-20261018','external.compatibility_build_completed'":
            "'external-windows-product-build-typed-query-v1-20261018','external.corrective_build_completed'",
        "'external-windows-source-storage-qualification-v1-20261018'":
            "'external-windows-typed-query-qualification-v1-20261018-owned-state-continuation'",
        "    source=timed_stage(old['stage_program'])":
            "    prior_slots={b['instance_id']:b['slot'] for b in old['blocks']}\n"
            "    old={**old,'blocks':development_blocks(old['blocks'])}\n"
            "    source=timed_stage(old['stage_program'])",
        "only(OLD+'-block-'+str(slot),'external.confirmation_stage_planned')":
            "only(OLD+'-block-'+str(prior_slots[identity]),'external.confirmation_stage_planned')",
        "'atmem-confirmation-amended19-v3-staging-v1'": "'atmem-corrective-development19-staging-v1'",
        "'confirmation19-v3-'+str(slot)": "'corrective-development19-'+str(slot)",
        "'all_76_cases_staged':len(results)==38": "'all_38_cases_staged':len(results)==19",
    }
    result = original
    for before, after in changes.items():
        if result.count(before) != 1:
            raise ValueError('exact exercised staging source required: '+before)
        result = result.replace(before, after)
    marker = "if __name__=='__main__':main()"
    if result.count(marker) != 1:
        raise ValueError('exact staging entry point required')
    result = result.replace(marker, 'SEED='+repr(SEED)+'\n'+inspect.getsource(development_blocks)+'\n'+marker)
    ast.parse(result, feature_version=(3, 10))
    return result
