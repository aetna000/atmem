from io import BytesIO
import zipfile
import pytest
from tools.retain_swebench_product_artifacts import wheel_metadata


def archive(name):
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w') as wheel:
        wheel.writestr(name, b'original product bytes')
    return stream.getvalue()


def test_artifact_metadata_is_for_original_complete_bytes():
    raw = archive('atmem/__init__.py')
    result = wheel_metadata(raw)
    assert result['bytes'] == len(raw) and result['members'] == 1
    assert len(result['sha256']) == 64


@pytest.mark.parametrize('name', ['../atmem.py', '/absolute/atmem.py', 'unrelated.py'])
def test_bad_product_members_refuse_before_retention(name):
    with pytest.raises(ValueError):
        wheel_metadata(archive(name))
