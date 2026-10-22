from pathlib import Path
import os

import pytest

from benchmarks.dolphinbench.subscription_service import private_output_root


@pytest.mark.parametrize('root',['/Volumes/AtMemDolphin','/Volumes/AtMemBenchRuntime'])
@pytest.mark.skipif(os.name=='nt',reason='Mac-only private subscription-controller volume allowlist; product Windows support is tested separately')
def test_private_output_supports_both_dedicated_benchmark_volumes(root):
    assert private_output_root(root+'/fixture/subscription')==Path(root+'/fixture/subscription')


@pytest.mark.parametrize('root',['/Volumes/MEM','/tmp','/Users','/Volumes/AtMemBenchRuntime-other'])
def test_other_output_roots_do_not_widen_private_transport_boundary(root):
    with pytest.raises(ValueError):private_output_root(root+'/fixture')
