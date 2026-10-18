import ast
from pathlib import Path
from benchmarks.code_replay.confirmation_staging import stage_program


def test_two_arm_stage_uses_fresh_real_home_and_exact_source_commit():
    source=stage_program()
    tree=ast.parse(source,feature_version=(3,9))
    assert "if arm=='atmem'" not in source and "cases['pack']" not in source
    assert 'generation_zlib_base64' in source and 'zlib.compress' in source
    assert 'max_context_bytes=4096' in source
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id=='cases' for t in n.targets))
    for arm in ('native','tools'):
        values=dict(cases={},arm=arm,case=Path('/block')/arm,workspace=Path('/block')/arm/'workspace',
                    operator=Path('/block')/arm/'operator',scope={},prepared={},generation='complete-compressed',
                    initial_commit='base',initial_tree='tree')
        exec(compile(ast.Module(body=[node],type_ignores=[]),'stage-descriptor','exec'),values)
        case=values['cases'][arm]
        assert case['atmem_home']==(None if arm=='native' else '/block/tools/atmem-home')
        assert case['database']==(None if arm=='native' else '/block/tools/atmem-home/memory.db')
        assert case['initial_commit']=='base'
