import subprocess
import pytest
from benchmarks.code_replay.confirmation_v3_capture import git_metadata,captured_case


def test_git_reference_bytes_without_executing_repository_hooks(tmp_path):
    subprocess.run(['git','init',str(tmp_path)],check=True,capture_output=True)
    (tmp_path/'main.py').write_text('pass\n')
    subprocess.run(['git','-C',str(tmp_path),'add','main.py'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=Test','-c','user.email=test@example.com','commit','-m','base'],check=True,capture_output=True)
    original=git_metadata(tmp_path)
    assert len(original['commit'])==40 and original['reference_path'].startswith('refs/heads/')
    (tmp_path/'.git/HEAD').write_text('ref: ../../outside\n')
    with pytest.raises(ValueError):git_metadata(tmp_path)


def test_reference_symlink_refused(tmp_path):
    (tmp_path/'.git').mkdir();(tmp_path/'.git/HEAD').symlink_to(tmp_path/'outside')
    with pytest.raises((ValueError,OSError)):git_metadata(tmp_path)


def test_capture_rejects_nonbenchmark_roots(tmp_path):
    with pytest.raises(ValueError,match='origin'):
        captured_case({'workspace':str(tmp_path),'root':str(tmp_path.parent)},writers_stopped=True)
