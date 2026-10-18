"""Reuse the verified MEM transfer with frozen, standalone CD1 recovery."""
import ast

from benchmarks.code_replay.corrective_controls import exact_changes, PREFIX

OUTPUT = '/Volumes/MEM/AtMem-Code-Replay-20261017/corrective-development-protected-20261018'
KEYS = '/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-20261017/keys-corrective-development-archive-20261018'


def recovery_program(archive, grade, audit):
    """A new process reads archives and keys only; live vault access is denied."""
    sources = {'benchmarks.code_replay.confirmation_v3_grade': grade,
               'benchmarks.code_replay.confirmation_v3_archive': archive}
    return '''import json,sys,types
from pathlib import Path
from benchmarks.code_replay import run_evidence
def forbidden(*args,**kwargs):raise RuntimeError('live evidence vault forbidden in standalone recovery')
run_evidence.operational_evidence=forbidden
sources='''+repr(sources)+'''
for name,source in sources.items():
    module=types.ModuleType(name);sys.modules[name]=module
    exec(compile(source,'<frozen-CD1-archive-reader>','exec'),module.__dict__)
archive=sys.modules['benchmarks.code_replay.confirmation_v3_archive']
proof=archive.recover_collection(Path('''+repr(OUTPUT)+'''),Path('''+repr(KEYS)+'''))
audit={}
exec(compile('''+repr(audit)+''','<frozen-CD1-original-request-audit>','exec'),audit)
proof['request_audit']=audit['audit_collection'](Path('''+repr(OUTPUT)+'''),Path('''+repr(KEYS)+'''))
if (proof['candidates'],proof['private_grades'],proof['public_vaults'])!=(38,38,38):raise ValueError('complete CD1 recovery required')
if proof['request_audit']['verified_original_requests']!=38:raise ValueError('all original CD1 requests required')
print(json.dumps(proof),flush=True)
'''


def transfer_source(original, archive, grade, audit):
    source = exact_changes(original, [
        ("RUN = 'external-windows-confirmation-v3-MEM-transfer-v1-20261018'", 'RUN = '+repr(PREFIX+'MEM-transfer-v1-20261018'), 1),
        ('external-windows-confirmation-v3-archive-v1-20261018', PREFIX+'archive-v1-20261018', 1),
        ('external-windows-confirmation-v3-models-v1-20261018', PREFIX+'models-v1-20261018', 1),
        ('confirmation-archive-v3', 'corrective-development-archive-v1', 3),
        ('confirmation-archive-keys-v3', 'corrective-development-archive-keys-v1', 2),
        ('windows-confirmation-v3-protected-20261018', 'corrective-development-protected-20261018', 1),
        ('keys-confirmation-v3-archive-20261018', 'keys-corrective-development-archive-20261018', 1),
        ("if Path(__file__).read_text() != job['driver_source']:", "if Path(__file__).read_text() != job['baseline_transfer_source']:", 1),
        ('!= (76, 76, 76)', '!= (38, 38, 38)', 1),
    ])
    main = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    programs = [n for n in main.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'program' for t in n.targets)]
    if len(programs) != 1:
        raise ValueError('one exact original independent-recovery program required')
    old = ast.get_source_segment(source, programs[0])
    source = source.replace(old, 'program = '+repr(recovery_program(archive, grade, audit)), 1)
    ast.parse(source, feature_version=(3, 10))
    return source
