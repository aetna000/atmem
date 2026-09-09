from pathlib import Path
import runpy

import pytest


release_metadata = runpy.run_path(str(Path(__file__).parents[1] / "tools/release_metadata.py"))["release_metadata"]


@pytest.mark.parametrize("version,bridge,channel,prerelease", [
    ("2.2.6", "2.2.6", "latest", "false"),
    ("2.3.0a1", "2.3.0-alpha.1", "alpha", "true"),
    ("2.3.0b2", "2.3.0-beta.2", "beta", "true"),
    ("2.3.0rc1", "2.3.0-rc.1", "rc", "true"),
])
def test_release_channel_matches_version(version, bridge, channel, prerelease):
    result = release_metadata(version, bridge, f"v{version}")
    assert result["npm_tag"] == channel
    assert result["prerelease"] == prerelease


@pytest.mark.parametrize("version,bridge,tag", [
    ("2.2.6", "2.2.6-beta.11", "v2.2.6"),
    ("2.3.0b2", "2.3.0-beta.1", "v2.3.0b2"),
    ("2.2.6", "2.2.6", "v2.2.7"),
    ("2.2.6+local", "2.2.6", "v2.2.6+local"),
])
def test_mismatched_or_unsupported_release_is_rejected(version, bridge, tag):
    with pytest.raises(ValueError):
        release_metadata(version, bridge, tag)
