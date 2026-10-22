from pathlib import Path

import pytest

from research.retrieval_2310.archive import collect, env_values


def test_archive_refuses_arbitrary_host_roots(tmp_path):
    with pytest.raises(ValueError, match='explicit campaign'):
        collect(tmp_path,tmp_path,[],tmp_path)


def test_env_parser_keeps_quoted_secret_local_without_emitting_it(tmp_path):
    path=tmp_path/'fixture.env'
    path.write_text('HF_TOKEN="fixture-not-a-real-token"\nOTHER=fixture\n# ignored\n')
    values=env_values(path)
    assert values == {'HF_TOKEN':'fixture-not-a-real-token','OTHER':'fixture'}
