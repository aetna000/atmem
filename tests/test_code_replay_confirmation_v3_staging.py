import ast
import pytest
from benchmarks.code_replay.confirmation_staging import stage_program
from benchmarks.code_replay.confirmation_v3_staging import timed_stage


def test_v3_timing_preserves_original_stage_except_observer_instrumentation():
    original=stage_program();timed=timed_stage(original)
    ast.parse(timed,feature_version=(3,10))
    restored=timed.replace('import base64,json,os,subprocess,zlib,time','import base64,json,os,subprocess,zlib')
    restored=restored.replace(' case_started=time.monotonic()\n','')
    restored=restored.replace("\n cases[arm]['stage_elapsed_ms']=int((time.monotonic()-case_started)*1000)",'')
    assert restored==original
    assert 'max_context_bytes=4096' in timed and 'experience=False' in timed


def test_changed_stage_is_not_silently_adapted():
    with pytest.raises(ValueError):timed_stage('an unqualified stage')
